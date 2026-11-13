"""collect_verification.py: period awareness and protected evidence paths."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

import duckdb

from tests import collect_verification as collect


class CollectVerificationTests(unittest.TestCase):
    def test_default_period_keeps_submitted_assertions(self):
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"PERIOD_START": "", "PERIOD_END": ""}):
            with duckdb.connect(str(Path(directory) / "empty.duckdb")) as db:
                months = collect.loaded_months(db)
        self.assertEqual(months, [(2025, m) for m in range(1, 7)])
        self.assertEqual(collect.expected_days(months), (181, "2025-01-01", "2025-06-30"))
        self.assertEqual(collect.NUMBER_WORDS[len(months)], "six")

    def test_months_come_from_batch_log(self):
        with TemporaryDirectory() as directory:
            with duckdb.connect(str(Path(directory) / "w.duckdb")) as db:
                db.execute("create table pipeline_batches as select * from (values "
                           "('2025-08'), ('2025-07'), ('2025-06')) t(month)")
                months = collect.loaded_months(db)
        self.assertEqual(months, [(2025, 6), (2025, 7), (2025, 8)])
        self.assertEqual(collect.expected_days(months), (92, "2025-06-01", "2025-08-31"))
        self.assertEqual(collect.expected_days([(2025, 1), (2025, 2), (2025, 3), (2025, 4),
                                                (2025, 5), (2025, 6), (2025, 7), (2025, 8)]),
                         (243, "2025-01-01", "2025-08-31"))
        self.assertEqual(collect.expected_days([(2025, 12), (2026, 1)]), (62, "2025-12-01", "2026-01-31"))

    def test_output_directory_is_required(self):
        argv = ["collect_verification.py", "--starting-commit", "x", "--branch", "y"]
        with patch.object(sys, "argv", argv), patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                collect.main()


if __name__ == "__main__":
    unittest.main()
