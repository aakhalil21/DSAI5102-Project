"""Incremental batch planning, the TLC source check, and safe no-op runs.

All HTTP is mocked; nothing here touches the network or the real warehouse.
"""

from datetime import datetime
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import requests

from ingestion import download_data, profile_data
from orchestration import pipeline
from streamlit.testing.v1 import AppTest
from tests.synthetic_fixture import ROOT, SCHEMA, trip


VALID_ZONES = b"LocationID,Borough,Zone,service_zone\n1,Manhattan,Test,Yellow Zone\n"
JUNE = (2025, 6)
JULY = (2025, 7)


def status(code):
    response = MagicMock()
    response.status_code = code
    response.__enter__.return_value = response
    return response


def loaded_months(last=JUNE):
    return download_data.month_range((2025, 1), last)


class MonthTests(unittest.TestCase):
    def test_next_month_and_year_rollover(self):
        self.assertEqual(download_data.next_month((2025, 6)), (2025, 7))
        self.assertEqual(download_data.next_month((2025, 12)), (2026, 1))
        self.assertEqual(
            download_data.month_range((2025, 11), (2026, 2)),
            [(2025, 11), (2025, 12), (2026, 1), (2026, 2)],
        )

    def test_invalid_month_and_reversed_period(self):
        with self.assertRaises(ValueError):
            download_data.parse_month("2025-13")
        with self.assertRaises(ValueError):
            download_data.configured_period({"PERIOD_START": "2025-06", "PERIOD_END": "2025-01"})

    def test_default_full_mode_files_and_period_are_unchanged(self):
        expected = {
            **{f"yellow_tripdata_2025-{m:02d}.parquet":
               f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-{m:02d}.parquet"
               for m in range(1, 7)},
            "taxi_zone_lookup.csv": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
        }
        months = download_data.month_range(*download_data.configured_period({}))
        self.assertEqual(download_data.data_files_for(months), expected)
        plan = pipeline.full_plan({})
        self.assertEqual((plan.period_start, plan.period_end), ("2025-01-01", "2025-07-01"))
        self.assertNotIn("batch_file", plan.dbt_vars())

    def test_default_profile_keeps_submitted_report(self):
        start, end = download_data.configured_period({})
        self.assertEqual(profile_data.period_label(start, end), "January-June 2025")
        self.assertEqual(profile_data.report_path(start, end), profile_data.REPORT_FILE)
        self.assertEqual(profile_data.period_label(JULY, JULY), "July 2025")
        self.assertEqual(
            profile_data.report_path(JULY, JULY),
            profile_data.EXTRA_REPORT_DIR / "data_profile_2025-07.md",
        )
        self.assertEqual(
            profile_data.period_label((2025, 11), (2026, 2)), "November 2025-February 2026"
        )


class PlanTests(unittest.TestCase):
    def test_next_month_after_last_loaded(self):
        plan, reason = pipeline.plan_incremental(loaded_months(), {})
        self.assertIsNone(reason)
        self.assertEqual(plan.batch, JULY)
        self.assertEqual(plan.months, loaded_months(JULY))
        values = plan.dbt_vars()
        self.assertEqual((values["period_start"], values["period_end"]), ("2025-01-01", "2025-08-01"))
        self.assertEqual(values["batch_file"], "yellow_tripdata_2025-07.parquet")
        self.assertEqual((values["batch_start"], values["batch_end"]), ("2025-07-01", "2025-08-01"))

    def test_december_rolls_over(self):
        plan, _ = pipeline.plan_incremental(download_data.month_range((2025, 1), (2025, 12)), {})
        self.assertEqual(plan.batch, (2026, 1))
        self.assertEqual(plan.dbt_vars()["period_end"], "2026-02-01")

    def test_max_month_cap(self):
        plan, reason = pipeline.plan_incremental(loaded_months(), {"MAX_MONTH": "2025-06"})
        self.assertIsNone(plan)
        self.assertIn("MAX_MONTH", reason)
        plan, _ = pipeline.plan_incremental(loaded_months(), {"MAX_MONTH": "2025-07"})
        self.assertEqual(plan.batch, JULY)

    def test_never_skips_ahead_or_accepts_gaps(self):
        with self.assertRaises(RuntimeError):
            pipeline.plan_incremental([(2025, 1), (2025, 3)], {})
        with self.assertRaises(RuntimeError):
            pipeline.plan_incremental(loaded_months(), {"PIPELINE_BATCH_MONTH": "2025-08"})
        with self.assertRaises(RuntimeError):
            pipeline.plan_incremental([], {})

    def test_explicit_rerun_of_loaded_month(self):
        plan, _ = pipeline.plan_incremental(loaded_months(), {"PIPELINE_BATCH_MONTH": "2025-03"})
        self.assertEqual(plan.batch, (2025, 3))
        self.assertEqual(plan.months, loaded_months())
        self.assertEqual(plan.dbt_vars()["period_end"], "2025-07-01")


class SourceCheckTests(unittest.TestCase):
    URL = download_data.trip_url(JULY)

    def test_published(self):
        with patch.object(download_data.requests, "head", return_value=status(200)) as head:
            self.assertTrue(download_data.check_month_published(self.URL))
        head.assert_called_once()

    def test_not_published(self):
        for code in (403, 404):
            with patch.object(download_data.requests, "head", return_value=status(code)):
                self.assertFalse(download_data.check_month_published(self.URL))

    def test_other_errors_fail(self):
        for code in (500, 503, 429):
            with patch.object(download_data.requests, "head", return_value=status(code)):
                with self.assertRaises(download_data.SourceCheckError):
                    download_data.check_month_published(self.URL)
        for error in (requests.Timeout("slow"), requests.ConnectionError("down")):
            with patch.object(download_data.requests, "head", side_effect=error):
                with self.assertRaises(download_data.SourceCheckError):
                    download_data.check_month_published(self.URL)

    def test_head_unsupported_falls_back_to_one_byte_get(self):
        with patch.object(download_data.requests, "head", return_value=status(405)), patch.object(
            download_data.requests, "get", return_value=status(206)
        ) as get:
            self.assertTrue(download_data.check_month_published(self.URL))
        self.assertEqual(get.call_args.kwargs["headers"], {"Range": "bytes=0-0"})

    def test_manifest_keeps_entries_outside_the_run(self):
        with TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "source_manifest.json").write_text(json.dumps({
                "yellow_tripdata_2025-07.parquet": {"rows": 1, "sha256": "x"}
            }))
            (raw / "taxi_zone_lookup.csv").write_bytes(VALID_ZONES)
            download_data.fetch_files({"taxi_zone_lookup.csv": "unused"}, raw)
            manifest = json.loads((raw / "source_manifest.json").read_text())
            self.assertEqual(set(manifest), {"yellow_tripdata_2025-07.parquet", "taxi_zone_lookup.csv"})


class IncrementalFlowTests(unittest.TestCase):
    """Run the incremental flow against a tiny live warehouse in a temp folder.

    Failure tests call the real Prefect flow so task errors and retries
    behave as in production; the others call the flow body directly.
    """

    def setUp(self):
        self.directory = TemporaryDirectory()
        root = Path(self.directory.name)
        self.raw = root / "raw"
        self.raw.mkdir()
        self.warehouse = root / "warehouse" / "nyc_taxi.duckdb"
        self.warehouse.parent.mkdir()
        self.candidate = self.warehouse.with_name("nyc_taxi_candidate.duckdb")
        self.lock = self.warehouse.parent / ".pipeline.lock"
        manifest = {}
        with duckdb.connect(str(self.warehouse)) as db:
            db.execute(f"""create table {pipeline.BATCH_TABLE} (
                month varchar, filename varchar, source_url varchar, sha256 varchar,
                source_rows bigint, accepted_rows bigint, rejected_rows bigint,
                status varchar, load_mode varchar, processed_at_utc timestamp)""")
            for month in loaded_months():
                name = download_data.trip_filename(month)
                path = self.raw / name
                pq.write_table(pa.Table.from_pylist(
                    [trip(datetime(*month, 2), datetime(*month, 2, 0, 10))], schema=SCHEMA), path)
                digest = download_data.checksum(path)
                manifest[name] = {"filename": name, "rows": 1, "sha256": digest,
                                  "source_url": download_data.trip_url(month)}
                db.execute(f"insert into {pipeline.BATCH_TABLE} values (?, ?, ?, ?, 1, 1, 0, 'loaded', 'full', now())",
                           [download_data.format_month(month), name, download_data.trip_url(month), digest])
        (self.raw / "source_manifest.json").write_text(json.dumps(manifest))
        self.before = self.warehouse.read_bytes()
        self.patches = [
            patch.object(pipeline, "RAW", self.raw),
            patch.object(pipeline, "WAREHOUSE", self.warehouse),
            patch.object(pipeline, "CANDIDATE", self.candidate),
            patch.object(pipeline, "LOCK", self.lock),
            patch.object(pipeline, "download_batch"),
            patch.object(pipeline, "profile_raw_data"),
            patch.object(pipeline, "build_dbt_models"),
            patch.object(pipeline, "validate_warehouse", return_value={}),
            patch.object(pipeline, "publish_warehouse"),
            patch.object(download_data.requests, "get", side_effect=AssertionError("no GET expected")),
            patch.dict("os.environ", {}, clear=False),
        ]
        self.mocks = [item.start() for item in self.patches]
        for name in ("MAX_MONTH", "PIPELINE_BATCH_MONTH", "PIPELINE_MODE"):
            os.environ.pop(name, None)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def assert_untouched(self):
        self.assertEqual(self.warehouse.read_bytes(), self.before)
        self.assertFalse(self.candidate.exists())
        self.assertFalse(self.lock.exists())
        pipeline.download_batch.assert_not_called()
        pipeline.build_dbt_models.assert_not_called()
        pipeline.publish_warehouse.assert_not_called()

    def test_not_published_is_successful_no_op(self):
        for code in (403, 404):
            with patch.object(download_data.requests, "head", return_value=status(code)):
                result = pipeline.nyc_taxi_pipeline.fn(mode="incremental")
            self.assertEqual(result["status"], "no_new_data")
            self.assertEqual(result["month"], "2025-07")
            self.assert_untouched()

    def test_max_month_reached_needs_no_http(self):
        with patch.dict("os.environ", {"MAX_MONTH": "2025-06"}), patch.object(
            download_data.requests, "head", side_effect=AssertionError("no HEAD expected")
        ):
            result = pipeline.nyc_taxi_pipeline.fn(mode="incremental")
        self.assertEqual(result["status"], "no_new_data")
        self.assert_untouched()

    def test_check_error_fails_after_retries(self):
        quick = pipeline.check_source_published.with_options(retry_delay_seconds=0)
        with patch.object(pipeline, "check_source_published", quick), patch.object(
            download_data.requests, "head", return_value=status(500)
        ) as head:
            with self.assertRaises(download_data.SourceCheckError):
                pipeline.nyc_taxi_pipeline(mode="incremental")
        self.assertEqual(head.call_count, 3)  # first attempt plus two retries
        self.assert_untouched()

    def test_published_goes_to_download_and_build(self):
        with patch.object(download_data.requests, "head", return_value=status(200)):
            result = pipeline.nyc_taxi_pipeline.fn(mode="incremental")
        self.assertEqual(result["status"], "loaded")
        pipeline.download_batch.assert_called_once_with(JULY)
        pipeline.profile_raw_data.assert_called_once_with(JULY)
        plan = pipeline.build_dbt_models.call_args.args[0]
        self.assertEqual((plan.mode, plan.batch, plan.months), ("incremental", JULY, loaded_months(JULY)))
        pipeline.publish_warehouse.assert_called_once()
        self.assertTrue(self.candidate.exists())  # copied from live before the build
        self.assertEqual(self.warehouse.read_bytes(), self.before)

    def test_changed_loaded_file_stops_the_run(self):
        path = self.raw / "yellow_tripdata_2025-03.parquet"
        pq.write_table(pa.Table.from_pylist(
            [trip(datetime(2025, 3, 3), datetime(2025, 3, 3, 0, 10))], schema=SCHEMA), path)
        with patch.object(download_data.requests, "head", return_value=status(200)):
            with self.assertRaisesRegex(RuntimeError, "Unexpected source change"):
                pipeline.nyc_taxi_pipeline(mode="incremental")
        self.assert_untouched()

    def test_missing_batch_log_asks_for_full_rebuild(self):
        with duckdb.connect(str(self.warehouse)) as db:
            db.execute(f"drop table {pipeline.BATCH_TABLE}")
        with self.assertRaisesRegex(RuntimeError, "full rebuild"):
            pipeline.nyc_taxi_pipeline.fn(mode="incremental")
        self.assertFalse(self.lock.exists())

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.nyc_taxi_pipeline.fn(mode="weekly")


class PublicationBlockedTests(unittest.TestCase):
    def test_blocked_replace_gives_clear_message_and_keeps_live(self):
        with TemporaryDirectory() as directory:
            published = Path(directory) / "published.duckdb"
            candidate = Path(directory) / "candidate.duckdb"
            for path, value in ((published, "old"), (candidate, "new")):
                with duckdb.connect(str(path)) as connection:
                    connection.execute(f"create table marker as select '{value}' as value")
            before = published.read_bytes()
            with patch.object(pipeline, "WAREHOUSE", published), patch.object(
                pipeline, "CANDIDATE", candidate
            ), patch.object(pipeline.os, "replace", side_effect=PermissionError("in use")):
                with self.assertRaisesRegex(RuntimeError, "Stop the dashboard"):
                    pipeline.publish_warehouse()
            self.assertEqual(published.read_bytes(), before)


class BatchProfileTests(unittest.TestCase):
    def test_incremental_profile_covers_only_the_batch_file(self):
        with TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "taxi_zone_lookup.csv").write_bytes(VALID_ZONES)
            pq.write_table(pa.Table.from_pylist([
                trip(datetime(2025, 7, 1), datetime(2025, 7, 1, 0, 10)),
                trip(datetime(2025, 8, 1), datetime(2025, 8, 1, 0, 10)),
            ], schema=SCHEMA), raw / "yellow_tripdata_2025-07.parquet")
            pq.write_table(pa.Table.from_pylist(
                [trip(datetime(2025, 6, 1), datetime(2025, 6, 1, 0, 10))], schema=SCHEMA,
            ), raw / "yellow_tripdata_2025-06.parquet")
            output = raw / "profile.md"
            with patch.object(profile_data, "RAW_DIR", raw), patch.object(
                profile_data, "ZONE_FILE", raw / "taxi_zone_lookup.csv"
            ):
                profile_data.main(JULY, JULY, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("# July 2025 Yellow Taxi Data Profile", text)
            self.assertIn("- Total rows: 2", text)
            self.assertIn("| Pickup timestamps outside July 2025 | 1 |", text)


class DashboardPeriodTests(unittest.TestCase):
    def build(self, database, with_batches):
        with duckdb.connect(str(database)) as connection:
            connection.execute("""
                create table fact_trips as select
                    date '2025-02-03' + cast(i as integer) as pickup_date,
                    'Unknown' as pickup_borough,
                    true as is_financial_adjustment,
                    false as is_financial_data_missing,
                    -1.0 as total_amount, -1.0 as fare_amount,
                    1.0 as trip_distance,
                    false as is_zero_distance,
                    false as is_unusually_long_distance,
                    false as is_unusually_long_duration,
                    10.0 as trip_duration_minutes
                from range(2) as t(i)
            """)
            if with_batches:
                connection.execute(f"""
                    create table {pipeline.BATCH_TABLE} as
                    select * from (values
                        ('2025-01', timestamp '2026-11-01 06:00:00'),
                        ('2025-07', timestamp '2026-11-13 06:05:00'))
                        as t(month, processed_at_utc)
                """)

    def captions(self, with_batches):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "warehouse.duckdb"
            self.build(database, with_batches)
            with patch.dict(os.environ, {"DASHBOARD_WAREHOUSE_PATH": str(database)}):
                app = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=30).run()
            self.assertFalse(app.exception)
            return [caption.value for caption in app.sidebar.caption]

    def test_period_comes_from_batch_log(self):
        captions = self.captions(True)
        self.assertIn("Data loaded: Jan 2025 – Jul 2025 · pickup records", captions)
        self.assertIn("Last batch processed: 13 Nov 2026 06:05 UTC", captions)

    def test_period_falls_back_to_accepted_dates(self):
        captions = self.captions(False)
        self.assertIn("Data loaded: Feb 2025 – Feb 2025 · pickup records", captions)
        self.assertFalse(any(text.startswith("Last batch") for text in captions))


if __name__ == "__main__":
    unittest.main()
