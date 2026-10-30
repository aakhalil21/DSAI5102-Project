"""Check source reuse, quarantine, and validation before finalization."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ingestion import download_data


VALID_ZONES = b"LocationID,Borough,Zone,service_zone\n1,Manhattan,Test,Yellow Zone\n"


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.payload


class SourceValidationTests(unittest.TestCase):
    def test_fresh_raw_directory_and_manifest_are_created(self):
        with TemporaryDirectory() as directory:
            raw = Path(directory) / "new" / "raw"
            with patch.object(download_data, "RAW_DATA_DIR", raw), patch.dict(
                download_data.DATA_FILES, {"taxi_zone_lookup.csv": "unused"}, clear=True
            ), patch.object(
                download_data.requests, "get", return_value=Response(VALID_ZONES)
            ):
                download_data.main()
            self.assertTrue((raw / "taxi_zone_lookup.csv").is_file())
            self.assertTrue((raw / "source_manifest.json").is_file())

    def test_valid_existing_file_is_preserved(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "taxi_zone_lookup.csv"
            destination.write_bytes(VALID_ZONES)
            with patch.object(download_data.requests, "get") as get:
                self.assertEqual(download_data.download_file("unused", destination), 1)
                get.assert_not_called()
            self.assertEqual(destination.read_bytes(), VALID_ZONES)

    def test_valid_existing_file_with_changed_checksum_is_rejected(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "taxi_zone_lookup.csv"
            destination.write_bytes(VALID_ZONES)
            expected = {"sha256": "not-the-current-checksum"}
            with self.assertRaises(RuntimeError):
                download_data.download_file("unused", destination, expected)

    def test_corrupt_existing_file_is_quarantined_before_replacement(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "taxi_zone_lookup.csv"
            destination.write_bytes(b"bad data")
            with patch.object(download_data.requests, "get", return_value=Response(VALID_ZONES)):
                self.assertEqual(download_data.download_file("unused", destination), 1)
            self.assertEqual(destination.read_bytes(), VALID_ZONES)
            copies = list(Path(directory).glob("*.invalid-*"))
            self.assertEqual(len(copies), 1)
            self.assertEqual(copies[0].read_bytes(), b"bad data")

    def test_invalid_download_is_never_finalized(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "taxi_zone_lookup.csv"
            with patch.object(download_data.requests, "get", return_value=Response(b"wrong,headers\n1,2\n")):
                with self.assertRaises(ValueError):
                    download_data.download_file("unused", destination)
            self.assertFalse(destination.exists())
            self.assertFalse(Path(str(destination) + ".part").exists())


if __name__ == "__main__":
    unittest.main()
