"""Build a tested candidate warehouse, then publish it atomically."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
from prefect import flow, task


ROOT = Path(__file__).resolve().parents[1]
TRANSFORMATIONS = ROOT / "transformations"
WAREHOUSE = ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"
CANDIDATE = WAREHOUSE.with_name("nyc_taxi_candidate.duckdb")
LOCK = WAREHOUSE.parent / ".pipeline.lock"
REQUIRED_TABLES = {
    "fact_trips", "rejected_trips", "dim_date", "dim_zone",
    "dim_payment_type", "mart_daily_performance", "mart_hourly_demand",
    "mart_zone_performance", "mart_payment_summary",
}


def run(command, cwd=ROOT, env=None):
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


@task(name="Validate raw source files", retries=2, retry_delay_seconds=10)
def download_raw_data():
    run([sys.executable, str(ROOT / "ingestion" / "download_data.py")])


@task(name="Profile raw taxi data")
def profile_raw_data():
    run([sys.executable, str(ROOT / "ingestion" / "profile_data.py")])


@task(name="Build and test candidate dbt models")
def build_dbt_models():
    executable = shutil.which("dbt")
    if executable is None:
        raise RuntimeError("The dbt executable was not found")
    run(
        [executable, "build", "--profiles-dir", "."],
        TRANSFORMATIONS,
        {**os.environ, "DBT_WAREHOUSE_PATH": str(CANDIDATE)},
    )


@task(name="Validate candidate warehouse")
def validate_warehouse():
    if not CANDIDATE.is_file():
        raise FileNotFoundError(CANDIDATE)
    with duckdb.connect(str(CANDIDATE), read_only=True) as connection:
        tables = {
            row[0] for row in connection.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            raise RuntimeError(f"Missing warehouse tables: {sorted(missing)}")
        manifest = json.loads(
            (ROOT / "data" / "raw" / "source_manifest.json").read_text(encoding="utf-8")
        )
        source = manifest["yellow_tripdata_2025-01.parquet"]["rows"]
        accepted = connection.execute("select count(*) from main.fact_trips").fetchone()[0]
        rejected = connection.execute("select count(*) from main.rejected_trips").fetchone()[0]
        daily = connection.execute("select count(*) from main.mart_daily_performance").fetchone()[0]
        if source != accepted + rejected:
            raise RuntimeError("Source count does not equal accepted plus rejected")
        if source == 0 or daily == 0:
            raise RuntimeError("Candidate warehouse is empty")
        for table in ("fact_trips", "rejected_trips"):
            bad = connection.execute(
                f"select count(*) - count(distinct trip_id) from main.{table}"
            ).fetchone()[0]
            if bad:
                raise RuntimeError(f"{table} has duplicate or null trip IDs")
    return {"source_rows": source, "fact_rows": accepted, "rejected_rows": rejected, "daily_rows": daily}


def publish_warehouse():
    # dbt's process and all validation readers are closed before replacement.
    with duckdb.connect(str(CANDIDATE)) as connection:
        connection.execute("checkpoint")
    if Path(str(CANDIDATE) + ".wal").exists():
        raise RuntimeError("Candidate WAL remains after checkpoint")
    # A running dashboard may hold the destination open on Windows. In that case
    # os.replace fails and the old database stays in place.
    os.replace(CANDIDATE, WAREHOUSE)


@flow(name="NYC Taxi End-to-End Pipeline", log_prints=True)
def nyc_taxi_pipeline():
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    try:
        LOCK.mkdir()
    except FileExistsError as error:
        raise RuntimeError(
            f"Another run holds {LOCK}; remove it manually only after checking that run has stopped"
        ) from error
    try:
        CANDIDATE.unlink(missing_ok=True)
        Path(str(CANDIDATE) + ".wal").unlink(missing_ok=True)
        download_raw_data()
        profile_raw_data()
        build_dbt_models()
        result = validate_warehouse()
        publish_warehouse()
        print(f"Published warehouse: {result}")
        return result
    finally:
        LOCK.rmdir()


if __name__ == "__main__":
    nyc_taxi_pipeline()
