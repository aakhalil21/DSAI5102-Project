"""Dashboard behavior and displayed metric values against read-only data."""

from datetime import date
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import duckdb
import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.py"
WAREHOUSE = ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"


def expected_values(start, end, borough=None):
    conditions = [
        "pickup_date between ? and ?",
        "not is_financial_adjustment",
        "not is_financial_data_missing",
    ]
    parameters = [start, end]
    if borough:
        conditions.append("pickup_borough = ?")
        parameters.append(borough)
    with duckdb.connect(str(WAREHOUSE), read_only=True) as db:
        count, charges, fare, distance, duration = db.execute(
            """
            select count(*), sum(total_amount), avg(fare_amount),
                avg(trip_distance) filter (
                    where not is_zero_distance and not is_unusually_long_distance
                ),
                avg(trip_duration_minutes) filter (
                    where not is_unusually_long_duration
                )
            from main.fact_trips where {}
            """.format(" and ".join(conditions)),
            parameters,
        ).fetchone()
    return [
        f"{count:,.0f}",
        (
            "—" if pd.isna(charges)
            else f"${charges / 1_000_000:,.2f}M"
            if abs(charges) >= 1_000_000
            else f"${charges:,.2f}"
        ),
        "—" if pd.isna(fare) else f"${fare:,.2f}",
        "—" if pd.isna(distance) else f"{distance:,.2f} mi",
        "—" if pd.isna(duration) else f"{duration:,.1f} min",
    ]


class DashboardTests(unittest.TestCase):
    def assert_metrics(self, app, start, end, borough=None):
        self.assertFalse(app.exception)
        self.assertEqual(
            [metric.value for metric in app.metric],
            expected_values(start, end, borough),
        )

    def test_filters_reset_and_values(self):
        app = AppTest.from_file(str(APP), default_timeout=30).run()
        with duckdb.connect(str(WAREHOUSE), read_only=True) as db:
            minimum, maximum = db.execute(
                "select min(pickup_date), max(pickup_date) from main.fact_trips"
            ).fetchone()
            boroughs = {
                row[0] for row in db.execute(
                    "select distinct pickup_borough from main.fact_trips "
                    "where pickup_borough is not null"
                ).fetchall()
            }
        self.assertTrue(boroughs.issubset(set(app.sidebar.selectbox[0].options)))
        self.assert_metrics(app, minimum, maximum)
        with duckdb.connect(str(WAREHOUSE), read_only=True) as db:
            exact_charges = db.execute(
                "select sum(total_amount) from main.fact_trips "
                "where not is_financial_adjustment "
                "and not is_financial_data_missing"
            ).fetchone()[0]
        self.assertIn(
            f"${exact_charges:,.2f}", app.metric[1].proto.help,
        )

        app.sidebar.date_input[0].set_value((minimum, minimum)).run()
        self.assert_metrics(app, minimum, minimum)

        week_end = date(2025, 1, 7)
        app.sidebar.date_input[0].set_value((minimum, week_end)).run()
        self.assert_metrics(app, minimum, week_end)

        app.sidebar.selectbox[0].set_value("Manhattan").run()
        self.assert_metrics(app, minimum, week_end, "Manhattan")

        app.sidebar.button[0].click().run()
        self.assertEqual(app.sidebar.selectbox[0].value, "All boroughs")
        self.assert_metrics(app, minimum, maximum)

    def test_empty_warehouse(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "empty.duckdb"
            with duckdb.connect(str(database)) as connection:
                connection.execute(
                    "create table fact_trips as select cast(null as date) as pickup_date where false"
                )
            with patch.dict(os.environ, {"DASHBOARD_WAREHOUSE_PATH": str(database)}):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.info)

    def test_no_eligible_results(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "ineligible.duckdb"
            with duckdb.connect(str(database)) as connection:
                connection.execute("""
                    create table fact_trips as select
                        date '2025-01-01' as pickup_date,
                        'Unknown' as pickup_borough,
                        true as is_financial_adjustment,
                        false as is_financial_data_missing,
                        -1.0 as total_amount, -1.0 as fare_amount,
                        1.0 as trip_distance,
                        false as is_zero_distance,
                        false as is_unusually_long_distance,
                        false as is_unusually_long_duration,
                        10.0 as trip_duration_minutes
                """)
            with patch.dict(os.environ, {"DASHBOARD_WAREHOUSE_PATH": str(database)}):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.info)
            self.assertFalse(app.metric)

    def test_missing_warehouse(self):
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.duckdb"
            with patch.dict(os.environ, {"DASHBOARD_WAREHOUSE_PATH": str(missing)}):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)


def build_synthetic_warehouse(database, with_batches=True):
    """Ten days, day d has (d + 1) * 1000 eligible trips; one Unknown payment."""
    with duckdb.connect(str(database)) as connection:
        connection.execute("""
            create table fact_trips as select
                date '2025-03-03' + cast(d as integer) as pickup_date,
                timestamp '2025-03-03 08:00:00'
                    + to_days(cast(d as integer)) as pickup_datetime,
                dayname(date '2025-03-03' + cast(d as integer)) as pickup_weekday,
                8 as pickup_hour,
                'Manhattan' as pickup_borough,
                'Midtown Center' as pickup_zone,
                161 as pickup_location_id,
                case when d = 0 and k = 0 then 5
                     when k % 4 = 0 then 2 else 1 end as payment_type,
                false as is_financial_adjustment,
                false as is_financial_data_missing,
                10.0 as total_amount, 8.0 as fare_amount, 0.0 as tip_percentage,
                1.0 as trip_distance,
                false as is_zero_distance,
                false as is_unusually_long_distance,
                false as is_unusually_long_duration,
                10.0 as trip_duration_minutes
            from range(10) as t(d) cross join range(10000) as u(k)
            where k < (d + 1) * 1000
        """)
        connection.execute("""
            create table dim_payment_type as select * from (values
                (1, 'Credit card'), (2, 'Cash'), (5, 'Unknown'))
                as t(payment_type_key, payment_type_name)
        """)
        if with_batches:
            connection.execute("""
                create table pipeline_batches as select * from (values
                    ('2025-01', 100, 90, 10, timestamp '2026-11-13 06:00:00'),
                    ('2025-02', 200, 150, 40, timestamp '2026-11-13 06:01:00'))
                    as t(month, source_rows, accepted_rows, rejected_rows,
                         processed_at_utc)
            """)


class DashboardPolishTests(unittest.TestCase):
    def run_app(self, with_batches=True):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "synthetic.duckdb"
            build_synthetic_warehouse(database, with_batches)
            with patch.dict(os.environ, {"DASHBOARD_WAREHOUSE_PATH": str(database)}):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
        self.assertFalse(app.exception)
        return app

    def figures(self, app):
        return [json.loads(chart.proto.spec) for chart in app.get("plotly_chart")]

    def test_payment_labels_show_count_and_share(self):
        payment = self.figures(self.run_app())[-1]
        labels = dict(zip(payment["data"][0]["y"], payment["data"][0]["text"]))
        self.assertEqual(labels["Unknown"], "1 · <0.1%")
        # Credit card 41,250 and cash 13,749 of 55,000 eligible trips.
        self.assertEqual(labels["Credit card"], "41,250 · 75.0%")
        self.assertEqual(labels["Cash"], "13,749 · 25.0%")
        shares = [
            float(text.split(" · ")[1].rstrip("%"))
            for text in labels.values() if "<" not in text
        ]
        self.assertAlmostEqual(sum(shares), 100, delta=0.1)

    def test_seven_day_average(self):
        daily_trips, daily_charges = self.figures(self.run_app())[:2]
        for figure, scale in ((daily_trips, 1), (daily_charges, 10)):
            self.assertEqual(
                [trace["name"] for trace in figure["data"]],
                ["Daily", "7-day average"],
            )
            average = figure["data"][1]["y"]
            self.assertEqual(len(average), 10)
            self.assertTrue(all(value is None for value in average[:6]))
            # Day 7 averages days 1-7: (1 + ... + 7) * 1000 / 7 = 4000.
            self.assertAlmostEqual(average[6], 4000 * scale)
            # Day 10 averages days 4-10: (4 + ... + 10) * 1000 / 7 = 7000.
            self.assertAlmostEqual(average[9], 7000 * scale)

    def test_short_range_has_no_average(self):
        app = self.run_app()
        app.sidebar.date_input[0].set_value(
            (date(2025, 3, 3), date(2025, 3, 8))
        ).run()
        self.assertFalse(app.exception)
        for figure in self.figures(app)[:2]:
            self.assertEqual(len(figure["data"]), 1)

    def test_pipeline_status_rows(self):
        app = self.run_app()
        tables = [
            frame.value for frame in app.dataframe
            if isinstance(frame.value, pd.DataFrame)
            and "Reconciles" in frame.value.columns
        ]
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(table["Month"].tolist(), ["Jan 2025", "Feb 2025"])
        self.assertEqual(table["Reconciles"].tolist(), ["Yes", "No"])
        self.assertEqual(
            table["Processed at (UTC)"].tolist(),
            ["2026-11-13 06:00", "2026-11-13 06:01"],
        )

    def test_pipeline_status_without_batch_log(self):
        app = self.run_app(with_batches=False)
        self.assertIn(
            "Batch log not available for this warehouse.",
            [caption.value for caption in app.caption],
        )
        self.assertFalse(any(
            "Reconciles" in getattr(frame.value, "columns", [])
            for frame in app.dataframe
        ))


if __name__ == "__main__":
    unittest.main()
