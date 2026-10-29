"""Dashboard behavior and displayed metric values against read-only data."""

from datetime import date
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


if __name__ == "__main__":
    unittest.main()
