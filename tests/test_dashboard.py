"""Smoke-test Streamlit date and borough filters against the published data."""

from datetime import date
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import duckdb
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


class DashboardTests(unittest.TestCase):
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

    def test_date_and_borough_filters(self):
        app = AppTest.from_file(str(APP), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 5)
        app.sidebar.date_input[0].set_value(
            (date(2025, 1, 1), date(2025, 1, 1))
        ).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 5)
        app.sidebar.date_input[0].set_value(
            (date(2025, 1, 1), date(2025, 1, 31))
        ).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 5)
        app.sidebar.selectbox[0].set_value("Manhattan").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 5)


if __name__ == "__main__":
    unittest.main()
