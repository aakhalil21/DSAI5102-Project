"""End-to-end incremental batch regression on synthetic data (no network).

Runs the real Prefect flow and real dbt against tiny monthly files in a
temporary folder and checks that:

* loading months one batch at a time ends in exactly the same warehouse
  state as a full rebuild of the same months, after every batch;
* extending the period re-evaluates earlier rejections (a July pickup in the
  June file is accepted once July is loaded; a March pickup with an unknown
  zone in the January file changes rejection reason when March is loaded);
* rerunning an already-loaded batch changes nothing;
* "not published yet", a failing dbt test, a failing candidate validation, a
  changed batch file and a changed loaded file all leave the live warehouse
  and batch log untouched;
* the batch log records the right files, checksums and counts.

The real data/raw, warehouse, dbt target and logs are never touched.
"""

import csv
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion import download_data  # noqa: E402
from orchestration import pipeline  # noqa: E402
from tests.synthetic_fixture import SCHEMA, trip  # noqa: E402


def row(pickup, dropoff, location=1, **changes):
    values = trip(pickup, dropoff, location)
    values.update(changes)
    return values


D = datetime
DUPLICATE = row(D(2025, 1, 15, 12), D(2025, 1, 15, 12, 10))
MONTH_ROWS = {
    1: [row(D(2025, 1, 1), D(2025, 1, 1, 0, 10)),
        DUPLICATE,
        row(D(2025, 1, 31, 23, 55), D(2025, 2, 1, 0, 5)),
        row(D(2024, 12, 31, 23, 55), D(2025, 1, 1, 0, 5)),       # before period: always rejected
        row(D(2025, 1, 5, 10), D(2025, 1, 5, 9)),                 # invalid timestamp order
        row(D(2025, 1, 6), D(2025, 1, 6, 0, 10), 999),            # unknown zone
        row(D(2025, 2, 3), D(2025, 2, 3, 0, 10), 2),              # accepted once Feb is loaded
        row(D(2025, 3, 4), D(2025, 3, 4, 0, 10), 999)],           # period -> unknown zone in March
    2: [row(D(2025, 2, 1), D(2025, 2, 1, 0, 10), 2),
        row(None, D(2025, 2, 2)),                                 # missing pickup
        row(D(2025, 2, 9), D(2025, 2, 9, 0, 20), payment_type=2, total_amount=-5.0)],
    3: [row(D(2025, 3, 1, 8), D(2025, 3, 1, 8, 30)),
        row(D(2025, 3, 2), D(2025, 3, 2, 0, 5), trip_distance=-1.0)],
    4: [row(D(2025, 4, 10, 18), D(2025, 4, 10, 18, 25), 2, payment_type=2)],
    5: [row(D(2025, 5, 17, 9), D(2025, 5, 17, 9, 40)),
        row(D(2025, 5, 31, 23, 59), D(2025, 6, 1, 0, 9), 2)],
    6: [DUPLICATE.copy(),
        row(D(2025, 6, 30, 23, 55), D(2025, 7, 1, 0, 5), 2),
        row(D(2025, 7, 1), D(2025, 7, 1, 0, 10)),                 # promoted when July loads
        row(D(2025, 8, 15), D(2025, 8, 15, 0, 10))],              # still rejected after July
    7: [row(D(2025, 7, 2), D(2025, 7, 2, 0, 15), 2),
        row(D(2025, 6, 30, 22), D(2025, 6, 30, 22, 30)),          # June pickup in July file
        row(D(2025, 7, 20), D(2025, 7, 20, 0, 30), fare_amount=None)],
}
GOOD_AUGUST = [row(D(2025, 8, 3), D(2025, 8, 3, 0, 10))]
BAD_AUGUST = [row(D(2025, 8, 4), D(2025, 8, 4, 0, 10), payment_type=None)]  # fails dbt tests

SNAPSHOT_TABLES = ("fact_trips", "rejected_trips", "dim_date", "dim_zone", "dim_payment_type",
                   "mart_daily_performance", "mart_hourly_demand", "mart_zone_performance",
                   "mart_payment_summary")


def write_month(raw, month, rows):
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA),
                   raw / download_data.trip_filename((2025, month)))


def snapshot(database):
    with duckdb.connect(str(database), read_only=True) as db:
        state = {}
        for table in SNAPSHOT_TABLES:
            state[table] = db.execute(f"select * from main.{table} order by all").fetchall()
        state["batches"] = db.execute(f"""
            select month, filename, source_url, sha256, source_rows, accepted_rows,
                rejected_rows, status
            from main.{pipeline.BATCH_TABLE} order by month
        """).fetchall()
        state["totals"] = db.execute("""
            select count(*), sum(total_amount) from main.fact_trips
            where not is_financial_adjustment and not is_financial_data_missing
        """).fetchone()
    return state


def batch_log(database):
    with duckdb.connect(str(database), read_only=True) as db:
        return db.execute(f"select * from main.{pipeline.BATCH_TABLE} order by month").fetchall()


def reason(database, pickup):
    with duckdb.connect(str(database), read_only=True) as db:
        accepted = db.execute("select source_filename from main.fact_trips "
                              "where pickup_datetime = ?", [pickup]).fetchall()
        rejected = db.execute("select source_filename, rejection_reason from main.rejected_trips "
                              "where pickup_datetime = ?", [pickup]).fetchall()
    return accepted, rejected


def assert_same(left, right, label):
    for key in left:
        assert left[key] == right[key], f"{label}: {key} differs\n{left[key]}\n{right[key]}"


class Fixture:
    def __init__(self, root):
        self.root = root
        self.raw = root / "raw"
        self.raw.mkdir()
        for month, rows in MONTH_ROWS.items():
            write_month(self.raw, month, rows)
        with (self.raw / "taxi_zone_lookup.csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(["LocationID", "Borough", "Zone", "service_zone"])
            writer.writerow([1, "Manhattan", "Shared Zone", "Yellow Zone"])
            writer.writerow([2, "Queens", "Shared Zone", "Yellow Zone"])
        self.head = MagicMock(side_effect=AssertionError("unexpected availability check"))

    def run(self, name, mode, **settings):
        """Run the real flow for warehouse ``name`` with the given env settings."""
        warehouse = self.root / name / "nyc_taxi.duckdb"
        warehouse.parent.mkdir(exist_ok=True)
        env = {key: "" for key in ("PERIOD_START", "PERIOD_END", "MAX_MONTH", "PIPELINE_BATCH_MONTH")}
        env.update(settings)

        def full_download():
            months = download_data.month_range(*download_data.configured_period())
            download_data.fetch_files(download_data.data_files_for(months), self.raw)

        with patch.dict(os.environ, env), \
                patch.object(pipeline, "RAW", self.raw), \
                patch.object(pipeline, "WAREHOUSE", warehouse), \
                patch.object(pipeline, "CANDIDATE", warehouse.with_name("nyc_taxi_candidate.duckdb")), \
                patch.object(pipeline, "LOCK", warehouse.parent / ".pipeline.lock"), \
                patch.object(pipeline, "download_raw_data", full_download), \
                patch.object(pipeline, "profile_raw_data", MagicMock()), \
                patch.object(download_data.requests, "head", self.head), \
                patch.object(download_data.requests, "get",
                             side_effect=AssertionError("no download expected")):
            return pipeline.nyc_taxi_pipeline(mode=mode), warehouse

    def expect_failure(self, name, message, **settings):
        warehouse = self.root / name / "nyc_taxi.duckdb"
        before, log = warehouse.read_bytes(), batch_log(warehouse)
        try:
            self.run(name, "incremental", **settings)
        except Exception as error:  # noqa: BLE001 - any failure must leave live intact
            print(f"Expected failure ({message}): {type(error).__name__}: {str(error)[:160]}")
        else:
            raise AssertionError(f"{message}: run should have failed")
        assert warehouse.read_bytes() == before, f"{message}: live warehouse changed"
        assert batch_log(warehouse) == log, f"{message}: batch log changed"
        assert not (warehouse.parent / ".pipeline.lock").exists()


def main():
    with TemporaryDirectory(prefix="taxi-incremental-") as directory:
        root = Path(directory)
        # Keep dbt artifacts and logs away from the real target/log folders.
        os.environ["DBT_TARGET_PATH"] = str(root / "dbt-target")
        os.environ["DBT_LOG_PATH"] = str(root / "dbt-logs")
        fixture = Fixture(root)

        # Equivalence after every batch: full Jan, then one month at a time.
        result, live = fixture.run("live", "full", PERIOD_END="2025-01")
        assert result["source_rows"] == 8, result
        for month in range(2, 7):
            result, _ = fixture.run("live", "incremental", MAX_MONTH="2025-06")
            assert result["status"] == "loaded" and result["month"] == f"2025-{month:02d}", result
            _, full = fixture.run(f"full-{month}", "full", PERIOD_END=f"2025-{month:02d}")
            assert_same(snapshot(live), snapshot(full), f"after 2025-{month:02d}")
            if month == 2:
                accepted, _ = reason(live, D(2025, 2, 3))
                assert accepted == [("yellow_tripdata_2025-01.parquet",)], accepted
            if month == 3:
                _, rejected = reason(live, D(2025, 3, 4))
                assert rejected == [("yellow_tripdata_2025-01.parquet", "unknown_pickup_location")], rejected
        print("Equivalence: incremental Jan..Jun matches a full rebuild after every batch")

        # Default full rebuild (PERIOD_START/END unset) equals the same months.
        _, default_full = fixture.run("default-full", "full")
        assert_same(snapshot(live), snapshot(default_full), "default full rebuild")

        # MAX_MONTH reached: no HTTP, no change.
        before = live.read_bytes()
        result, _ = fixture.run("live", "incremental", MAX_MONTH="2025-06")
        assert result["status"] == "no_new_data", result
        assert live.read_bytes() == before
        fixture.head.assert_not_called()

        # Idempotency: rerun the last and an earlier batch.
        state = snapshot(live)
        log = batch_log(live)
        for month in ("2025-06", "2025-03"):
            fixture.run("live", "incremental", PIPELINE_BATCH_MONTH=month)
            assert_same(state, snapshot(live), f"rerun {month}")
        after = batch_log(live)
        changed = [old[0] for old, new in zip(log, after) if old != new]
        assert changed == ["2025-03", "2025-06"], changed  # only processed_at/load_mode of reruns
        assert [r[:8] for r in log] == [r[:8] for r in after]
        print("Idempotency: rerunning 2025-06 and 2025-03 left every table unchanged")

        # Period extension: July promotes the June-file July pickup.
        accepted, rejected = reason(live, D(2025, 7, 1))
        assert not accepted and rejected == [("yellow_tripdata_2025-06.parquet",
                                              "pickup_outside_project_period")], rejected
        result, _ = fixture.run("live", "incremental")
        assert result["month"] == "2025-07", result
        accepted, rejected = reason(live, D(2025, 7, 1))
        assert accepted == [("yellow_tripdata_2025-06.parquet",)] and not rejected
        _, rejected = reason(live, D(2025, 8, 15))
        assert rejected == [("yellow_tripdata_2025-06.parquet", "pickup_outside_project_period")]
        _, full7 = fixture.run("full-7", "full", PERIOD_END="2025-07")
        assert_same(snapshot(live), snapshot(full7), "after 2025-07")
        print("Period extension: July load matches a full Jan..Jul rebuild")

        # Batch log contents.
        manifest = json.loads((fixture.raw / "source_manifest.json").read_text())
        expected_counts = {"2025-01": (8, 4, 4), "2025-02": (3, 2, 1), "2025-03": (2, 1, 1),
                           "2025-04": (1, 1, 0), "2025-05": (2, 2, 0), "2025-06": (4, 3, 1),
                           "2025-07": (3, 3, 0)}
        for entry in batch_log(live):
            month, filename, url, sha, source, good, bad, status, mode, processed = entry
            assert filename == f"yellow_tripdata_{month}.parquet", entry
            assert url == download_data.trip_url(download_data.parse_month(month)), entry
            assert sha == manifest[filename]["sha256"] == download_data.checksum(fixture.raw / filename)
            assert (source, good, bad) == expected_counts[month], entry
            assert status == "loaded" and processed is not None, entry
            assert mode == ("full" if month == "2025-01" else "incremental"), entry
        print("Batch log: files, URLs, checksums and per-file counts are correct")

        # Not published yet: 404 for August, warehouse untouched.
        fixture.head.side_effect = None
        fixture.head.return_value = MagicMock(status_code=404)
        before = live.read_bytes()
        result, _ = fixture.run("live", "incremental")
        assert result == {"status": "no_new_data", "month": "2025-08",
                          "reason": "yellow_tripdata_2025-08.parquet is not published yet"}, result
        assert live.read_bytes() == before
        fixture.head.side_effect = AssertionError("unexpected availability check")

        # A batch that fails dbt tests (null payment type in an accepted trip).
        write_month(fixture.raw, 8, BAD_AUGUST)
        fixture.expect_failure("live", "dbt test failure")

        # The bad August file is now recorded in the manifest; replacing it is
        # an unexpected source change and stops the run.
        write_month(fixture.raw, 8, GOOD_AUGUST)
        fixture.expect_failure("live", "changed batch file")
        manifest = json.loads((fixture.raw / "source_manifest.json").read_text())
        del manifest["yellow_tripdata_2025-08.parquet"]
        (fixture.raw / "source_manifest.json").write_text(json.dumps(manifest))

        # A changed, already-loaded file also stops the run.
        march = fixture.raw / "yellow_tripdata_2025-03.parquet"
        original = march.read_bytes()
        write_month(fixture.raw, 3, MONTH_ROWS[3][:1])
        fixture.expect_failure("live", "changed loaded file")
        march.write_bytes(original)

        # A batch that fails candidate validation after a complete dbt build.
        real_validate = pipeline.validate_warehouse

        def failing_validation(plan=None):
            real_validate.fn(plan)
            raise RuntimeError("simulated candidate validation failure")

        with patch.object(pipeline, "validate_warehouse", failing_validation):
            fixture.expect_failure("live", "validation failure")

        # Finally the good August batch loads and still matches a full rebuild.
        result, _ = fixture.run("live", "incremental")
        assert result["month"] == "2025-08" and result["source_rows"] == 24, result
        _, full8 = fixture.run("full-8", "full", PERIOD_END="2025-08")
        assert_same(snapshot(live), snapshot(full8), "after 2025-08")
        print("Failure safety: dbt-test, validation and checksum failures left live data and "
              "the batch log unchanged; August then loaded and matches a full rebuild")
        print("Synthetic incremental fixture passed")


if __name__ == "__main__":
    main()
