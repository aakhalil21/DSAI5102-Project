"""Check that validation failure preserves a published database."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import duckdb

from orchestration import pipeline


class PublicationTests(unittest.TestCase):
    def test_fresh_warehouse_directory_is_created(self):
        with TemporaryDirectory() as directory:
            warehouse = Path(directory) / "new" / "warehouse" / "published.duckdb"
            candidate = warehouse.with_name("candidate.duckdb")
            lock = warehouse.parent / ".pipeline.lock"
            with patch.object(pipeline, "WAREHOUSE", warehouse), patch.object(
                pipeline, "CANDIDATE", candidate
            ), patch.object(pipeline, "LOCK", lock), patch.object(
                pipeline, "download_raw_data"
            ), patch.object(pipeline, "profile_raw_data"), patch.object(
                pipeline, "build_dbt_models"
            ), patch.object(pipeline, "validate_warehouse", return_value={}):
                with patch.object(pipeline, "publish_warehouse"):
                    pipeline.nyc_taxi_pipeline.fn()
            self.assertTrue(warehouse.parent.is_dir())
            self.assertFalse(lock.exists())

    def test_failure_preserves_published_file_and_success_replaces_it(self):
        with TemporaryDirectory() as directory:
            published = Path(directory) / "published.duckdb"
            candidate = Path(directory) / "candidate.duckdb"
            with duckdb.connect(str(published)) as connection:
                connection.execute("create table marker as select 'old' as value")
            with duckdb.connect(str(candidate)) as connection:
                connection.execute("create table marker as select 'new' as value")
            before = published.read_bytes()
            with patch.object(pipeline, "WAREHOUSE", published), patch.object(
                pipeline, "CANDIDATE", candidate
            ):
                with self.assertRaises(RuntimeError):
                    pipeline.validate_warehouse.fn()
                self.assertEqual(published.read_bytes(), before)
                pipeline.publish_warehouse()
                with duckdb.connect(str(published), read_only=True) as connection:
                    self.assertEqual(
                        connection.execute("select value from marker").fetchone()[0],
                        "new",
                    )


if __name__ == "__main__":
    unittest.main()
