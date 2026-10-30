"""Download and validate January-June 2025 source files."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DATA_FILES = {
    **{
        f"yellow_tripdata_2025-{month:02d}.parquet":
        f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-{month:02d}.parquet"
        for month in range(1, 7)
    },
    "taxi_zone_lookup.csv": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
}
TRIP_TYPES = {
    "VendorID": "INTEGER", "tpep_pickup_datetime": "TIMESTAMP",
    "tpep_dropoff_datetime": "TIMESTAMP", "passenger_count": "DOUBLE",
    "trip_distance": "DOUBLE", "RatecodeID": "DOUBLE",
    "store_and_fwd_flag": "VARCHAR", "PULocationID": "INTEGER",
    "DOLocationID": "INTEGER", "payment_type": "BIGINT",
    "fare_amount": "DOUBLE", "extra": "DOUBLE", "mta_tax": "DOUBLE",
    "tip_amount": "DOUBLE", "tolls_amount": "DOUBLE",
    "improvement_surcharge": "DOUBLE", "total_amount": "DOUBLE",
    "congestion_surcharge": "DOUBLE", "Airport_fee": "DOUBLE",
    "cbd_congestion_fee": "DOUBLE",
}
ZONE_HEADERS = ["LocationID", "Borough", "Zone", "service_zone"]


def validate_trip_file(path):
    """Check the complete Parquet scan and the fields dbt needs to cast."""
    with duckdb.connect() as connection:
        rows = connection.execute(
            "describe select * from read_parquet(?)", [str(path)]
        ).fetchall()
        schema = {row[0]: row[1].upper() for row in rows}
        missing = set(TRIP_TYPES) - set(schema)
        if missing:
            raise ValueError(f"Missing Parquet columns: {sorted(missing)}")
        for column, expected in TRIP_TYPES.items():
            actual = schema[column]
            if expected == "DOUBLE":
                valid = actual in {"DOUBLE", "FLOAT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT"} or actual.startswith("DECIMAL(")
            elif expected in {"INTEGER", "BIGINT"}:
                valid = actual in {"INTEGER", "BIGINT", "SMALLINT", "TINYINT", "UINTEGER", "UBIGINT"}
            elif expected == "TIMESTAMP":
                valid = actual.startswith("TIMESTAMP")
            else:
                valid = actual == expected
            if not valid:
                raise ValueError(f"Parquet column {column}: expected {expected}, got {actual}")
        count = connection.execute(
            "select count(*), sum(length(to_json(t))) from read_parquet(?) as t",
            [str(path)]
        ).fetchone()[0]
        if count == 0:
            raise ValueError("Parquet file contains no records")
        return count


def validate_zone_file(path):
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ZONE_HEADERS:
            raise ValueError(f"Taxi-zone CSV headers must be {ZONE_HEADERS}; got {reader.fieldnames}")
        seen = set()
        count = 0
        for row in reader:
            value = row["LocationID"]
            if value is None or not value.strip():
                raise ValueError(f"Missing LocationID at CSV row {count + 2}")
            try:
                location_id = int(value)
            except ValueError as error:
                raise ValueError(f"Invalid LocationID at CSV row {count + 2}: {value}") from error
            if location_id in seen:
                raise ValueError(f"Duplicate LocationID: {location_id}")
            seen.add(location_id)
            count += 1
        if count == 0:
            raise ValueError("Taxi-zone CSV contains no records")
        return count


def validate_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty source file: {path}")
    try:
        return validate_trip_file(path) if path.suffix == ".parquet" else validate_zone_file(path)
    except (duckdb.Error, UnicodeError, csv.Error) as error:
        raise ValueError(f"Unusable source file {path.name}: {error}") from error


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url, destination, expected=None):
    """Reuse a valid file; quarantine invalid content; publish validated bytes."""
    if destination.exists():
        try:
            count = validate_file(destination)
            current_checksum = checksum(destination)
            if expected and expected.get("sha256") != current_checksum:
                raise RuntimeError(
                    f"Unexpected source change for {destination.name}: checksum does not match "
                    "the existing manifest. Review the file before accepting a new source version."
                )
            print(f"Validated existing {destination.name}: {count:,} rows")
            return count
        except ValueError as error:
            quarantine = destination.with_name(
                destination.name + ".invalid-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            )
            destination.replace(quarantine)
            print(f"Quarantined {destination.name} as {quarantine.name}: {error}")

    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        count = validate_trip_file(temporary) if destination.suffix == ".parquet" else validate_zone_file(temporary)
        new_checksum = checksum(temporary)
        if expected and expected.get("sha256") != new_checksum:
            raise RuntimeError(
                f"Downloaded source changed for {destination.name}: checksum does not match "
                "the existing manifest. Review the upstream change before accepting it."
            )
        temporary.replace(destination)
        print(f"Downloaded and validated {destination.name}: {count:,} rows")
        return count
    finally:
        temporary.unlink(missing_ok=True)


def main():
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = RAW_DATA_DIR / "source_manifest.json"
    previous = {}
    if manifest.exists():
        try:
            previous = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise ValueError(f"Invalid source manifest: {manifest}") from error
    metadata = {}
    for filename, url in DATA_FILES.items():
        path = RAW_DATA_DIR / filename
        count = download_file(url, path, previous.get(filename))
        metadata[filename] = {
            "filename": filename, "source_url": url, "rows": count,
            "size_bytes": path.stat().st_size, "sha256": checksum(path),
        }
    temporary_manifest = manifest.with_suffix(".json.part")
    temporary_manifest.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    temporary_manifest.replace(manifest)
    print("Initial data validation completed successfully.")


if __name__ == "__main__":
    main()
