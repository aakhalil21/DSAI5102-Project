"""Exercise rejection, duplicate, and financial rules in an isolated dbt build."""

import csv
from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FIXTURE = ROOT / "data" / "warehouse" / "synthetic_fixture.parquet"
DATABASE = ROOT / "data" / "warehouse" / "synthetic_fixture.duckdb"


def main():
    parquet = pq.ParquetFile(RAW / "yellow_tripdata_2025-01.parquet")
    first = next(parquet.iter_batches(batch_size=1)).to_pylist()[0]
    with (RAW / "taxi_zone_lookup.csv").open(newline="", encoding="utf-8-sig") as source:
        zone = int(next(csv.DictReader(source))["LocationID"])
    first.update({
        "tpep_pickup_datetime": datetime(2025, 1, 15, 12),
        "tpep_dropoff_datetime": datetime(2025, 1, 15, 12, 10),
        "PULocationID": zone, "DOLocationID": zone,
        "trip_distance": 1, "fare_amount": 8, "total_amount": 10,
        "tip_amount": 2, "payment_type": 1,
    })
    rows = [first.copy() for _ in range(9)]
    rows[2]["tpep_pickup_datetime"] = None
    rows[3]["tpep_dropoff_datetime"] = datetime(2025, 1, 15, 11)
    rows[4]["PULocationID"] = None
    rows[5]["DOLocationID"] = 999999
    rows[6]["fare_amount"] = -8
    rows[6]["total_amount"] = -10
    rows[7]["total_amount"] = None
    rows[8]["fare_amount"] = 0
    rows[8]["total_amount"] = 0
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=parquet.schema_arrow), FIXTURE)
    DATABASE.unlink(missing_ok=True)
    env = {
        **os.environ,
        "DBT_TRIP_SOURCE": str(FIXTURE),
        "DBT_ZONE_SOURCE": str(RAW / "taxi_zone_lookup.csv"),
        "DBT_WAREHOUSE_PATH": str(DATABASE),
    }
    subprocess.run(
        ["dbt", "build", "--profiles-dir", "."],
        cwd=ROOT / "transformations", env=env, check=True,
    )
    with duckdb.connect(str(DATABASE), read_only=True) as db:
        facts = db.execute("select count(*) from main.fact_trips").fetchone()[0]
        rejected = db.execute("select count(*) from main.rejected_trips").fetchone()[0]
        reasons = {
            row[0] for row in db.execute(
                "select rejection_reason from main.rejected_trips"
            ).fetchall()
        }
        if (facts, rejected) != (5, 4):
            raise AssertionError((facts, rejected))
        if reasons != {
            "missing_pickup_timestamp", "invalid_timestamp_order",
            "missing_pickup_location", "unknown_dropoff_location",
        }:
            raise AssertionError(reasons)
        daily = db.execute("""
            select accepted_record_count, standard_trip_count,
                financial_adjustment_count, total_revenue
            from main.mart_daily_performance
        """).fetchone()
        if daily != (5, 3, 1, 20):
            raise AssertionError(daily)
        duplicates = db.execute("""
            select coalesce(sum(record_count), 0) from (
                select count(*) as record_count
                from main.fact_trips
                group by content_fingerprint
                having count(*) > 1
            )
        """).fetchone()[0]
        if duplicates != 2:
            raise AssertionError(duplicates)
    print("Synthetic fixture passed: 5 accepted, 4 rejected, 2 duplicate-content rows, $20 eligible charges")


if __name__ == "__main__":
    main()
