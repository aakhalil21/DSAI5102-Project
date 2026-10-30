"""Self-contained six-month boundary and identity regression."""

import csv
from datetime import date, datetime
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = pa.schema([
    ("VendorID", pa.int32()), ("tpep_pickup_datetime", pa.timestamp("us")),
    ("tpep_dropoff_datetime", pa.timestamp("us")), ("passenger_count", pa.float64()),
    ("trip_distance", pa.float64()), ("RatecodeID", pa.float64()),
    ("store_and_fwd_flag", pa.string()), ("PULocationID", pa.int32()),
    ("DOLocationID", pa.int32()), ("payment_type", pa.int64()),
    ("fare_amount", pa.float64()), ("extra", pa.float64()),
    ("mta_tax", pa.float64()), ("tip_amount", pa.float64()),
    ("tolls_amount", pa.float64()), ("improvement_surcharge", pa.float64()),
    ("total_amount", pa.float64()), ("congestion_surcharge", pa.float64()),
    ("Airport_fee", pa.float64()), ("cbd_congestion_fee", pa.float64()),
])


def trip(pickup, dropoff, location=1):
    return {
        "VendorID": 1, "tpep_pickup_datetime": pickup,
        "tpep_dropoff_datetime": dropoff, "passenger_count": 1.0,
        "trip_distance": 1.0, "RatecodeID": 1.0,
        "store_and_fwd_flag": "N", "PULocationID": location,
        "DOLocationID": location, "payment_type": 1,
        "fare_amount": 8.0, "extra": 0.0, "mta_tax": 0.0,
        "tip_amount": 2.0, "tolls_amount": 0.0,
        "improvement_surcharge": 0.0, "total_amount": 10.0,
        "congestion_surcharge": 0.0, "Airport_fee": 0.0,
        "cbd_congestion_fee": 0.0,
    }


def main():
    with TemporaryDirectory(prefix="taxi-six-month-") as directory:
        root = Path(directory)
        raw = root / "raw"
        raw.mkdir()
        project = root / "transformations"
        shutil.copytree(ROOT / "transformations", project,
                        ignore=shutil.ignore_patterns("target", "logs", "dbt_packages"))
        duplicate = trip(datetime(2025, 1, 15, 12), datetime(2025, 1, 15, 12, 10))
        rows = {
            "01": [trip(datetime(2025, 1, 1), datetime(2025, 1, 1, 0, 10)),
                   duplicate,
                   trip(datetime(2025, 1, 31, 23, 55), datetime(2025, 2, 1, 0, 5)),
                   trip(datetime(2024, 12, 31, 23, 55), datetime(2025, 1, 1, 0, 5))],
            "02": [trip(datetime(2025, 2, 1), datetime(2025, 2, 1, 0, 10), 2)],
            "06": [duplicate.copy(),
                   trip(datetime(2025, 6, 30, 23, 55), datetime(2025, 7, 1, 0, 5), 2),
                   trip(datetime(2025, 7, 1), datetime(2025, 7, 1, 0, 10))],
        }
        for month, month_rows in rows.items():
            pq.write_table(pa.Table.from_pylist(month_rows, schema=SCHEMA),
                           raw / f"yellow_tripdata_2025-{month}.parquet")
        zone = raw / "taxi_zone_lookup.csv"
        with zone.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(["LocationID", "Borough", "Zone", "service_zone"])
            writer.writerow([1, "Manhattan", "Shared Zone", "Yellow Zone"])
            writer.writerow([2, "Queens", "Shared Zone", "Yellow Zone"])
        database = root / "fixture.duckdb"
        env = {**os.environ,
               "DBT_TRIP_SOURCE": str(raw / "yellow_tripdata_2025-0[1-6].parquet"),
               "DBT_ZONE_SOURCE": str(zone), "DBT_WAREHOUSE_PATH": str(database)}
        subprocess.run(["dbt", "build", "--profiles-dir", "."],
                       cwd=project, env=env, check=True)
        with duckdb.connect(str(database), read_only=True) as db:
            counts = db.execute("""
                select source_filename, count(*),
                    count(*) filter (where rejection_reason is null),
                    count(*) filter (where rejection_reason is not null)
                from main.int_trip_quality group by source_filename order by source_filename
            """).fetchall()
            assert counts == [
                ("yellow_tripdata_2025-01.parquet", 4, 3, 1),
                ("yellow_tripdata_2025-02.parquet", 1, 1, 0),
                ("yellow_tripdata_2025-06.parquet", 3, 2, 1)], counts
            assert sum(row[1] for row in counts) == 8
            assert sum(row[2] for row in counts) == 6
            assert sum(row[3] for row in counts) == 2
            reasons = db.execute("""
                select rejection_reason, count(*) from main.rejected_trips
                group by rejection_reason order by rejection_reason
            """).fetchall()
            assert reasons == [("pickup_outside_project_period", 2)], reasons
            duplicates = db.execute("""
                select source_filename, trip_id, content_fingerprint
                from main.fact_trips
                where pickup_datetime = timestamp '2025-01-15 12:00:00'
                order by source_filename
            """).fetchall()
            assert len(duplicates) == 2, duplicates
            assert duplicates[0][0] != duplicates[1][0]
            assert duplicates[0][1] != duplicates[1][1]
            assert duplicates[0][2] == duplicates[1][2]
            boundary = db.execute("""
                select count(*) from main.fact_trips
                where pickup_datetime = timestamp '2025-01-01 00:00:00'
                   or (pickup_datetime = timestamp '2025-06-30 23:55:00'
                       and dropoff_datetime = timestamp '2025-07-01 00:05:00')
            """).fetchone()[0]
            assert boundary == 2, boundary
            locations = db.execute("""
                select pickup_location_id, pickup_borough, count(*)
                from main.fact_trips group by 1, 2 order by 1
            """).fetchall()
            assert locations == [(1, "Manhattan", 4), (2, "Queens", 2)], locations
            cross_month = db.execute("""
                select count(*), sum(total_amount) from main.fact_trips
                where pickup_date between date '2025-01-31' and date '2025-02-01'
                  and not is_financial_adjustment and not is_financial_data_missing
            """).fetchone()
            assert cross_month == (2, 20.0), cross_month
        with patch.dict(os.environ, {"DASHBOARD_WAREHOUSE_PATH": str(database)}):
            app = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=30).run()
            assert not app.exception, app.exception
            app.sidebar.date_input[0].set_value((date(2025, 1, 31), date(2025, 2, 1))).run()
            assert not app.exception, app.exception
            assert app.metric[0].value == "2", app.metric[0].value
            assert app.metric[1].value == "$20.00", app.metric[1].value
        print("Synthetic fixture passed: 8 source = 6 accepted + 2 rejected; "
              "duplicate-content IDs retained; period and dashboard month boundaries verified")


if __name__ == "__main__":
    main()
