"""Build a tested candidate warehouse, then publish it atomically.

Two run modes (``PIPELINE_MODE`` or the flow's ``mode`` parameter):

* ``full`` (default): rebuild every month from ``PERIOD_START`` to
  ``PERIOD_END`` (default 2025-01 to 2025-06) into a fresh candidate.
* ``incremental``: load the single next monthly TLC file after the last month
  in the ``pipeline_batches`` log, if it has been published, into a copy of
  the live warehouse. "No new data" is a normal, successful outcome.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

import duckdb
from prefect import flow, task


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion import download_data  # noqa: E402
from ingestion.download_data import (  # noqa: E402
    format_month, month_range, next_month, parse_month, trip_filename,
)

TRANSFORMATIONS = ROOT / "transformations"
RAW = ROOT / "data" / "raw"
WAREHOUSE = ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"
CANDIDATE = WAREHOUSE.with_name("nyc_taxi_candidate.duckdb")
LOCK = WAREHOUSE.parent / ".pipeline.lock"
BATCH_TABLE = "pipeline_batches"
REQUIRED_TABLES = {
    "fact_trips", "rejected_trips", "dim_date", "dim_zone",
    "dim_payment_type", "mart_daily_performance", "mart_hourly_demand",
    "mart_zone_performance", "mart_payment_summary", BATCH_TABLE,
}
MODES = ("full", "incremental")


@dataclass
class RunPlan:
    """What one run builds: every loaded month and, if incremental, the batch."""

    mode: str
    months: list
    batch: Optional[tuple] = None
    notes: list = field(default_factory=list)

    @property
    def files(self):
        return [trip_filename(month) for month in self.months]

    @property
    def period_start(self):
        return month_start(self.months[0])

    @property
    def period_end(self):
        """Exclusive end date of the project period."""
        return month_start(next_month(self.months[-1]))

    def dbt_vars(self):
        values = {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "trip_files": [str(RAW / name) for name in self.files],
        }
        if self.batch is not None:
            values.update({
                "batch_file": trip_filename(self.batch),
                "batch_start": month_start(self.batch),
                "batch_end": month_start(next_month(self.batch)),
            })
        return values


def month_start(month):
    return f"{format_month(month)}-01"


@contextmanager
def measured_stage(timings, name):
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = round(time.perf_counter() - started, 3)


def save_optional_timings(path, timings):
    if not path:
        return
    try:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(timings, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"Optional pipeline timing could not be saved: {error}", file=sys.stderr)


def run(command, cwd=ROOT, env=None):
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------

def full_plan(environ=None):
    start, end = download_data.configured_period(environ)
    return RunPlan("full", month_range(start, end))


def read_batch_log(database):
    """Return the batch log of a warehouse as a list of dicts ordered by month."""
    if not Path(database).is_file():
        raise RuntimeError(
            f"No published warehouse at {database}. Run a full rebuild first "
            "(docker compose run --rm pipeline)."
        )
    with duckdb.connect(str(database), read_only=True) as connection:
        exists = connection.execute(
            "select count(*) from information_schema.tables "
            "where table_schema = 'main' and table_name = ?", [BATCH_TABLE]
        ).fetchone()[0]
        if not exists:
            raise RuntimeError(
                f"The warehouse has no {BATCH_TABLE} log (built before incremental "
                "loading existed). Run a full rebuild first (docker compose run --rm pipeline)."
            )
        cursor = connection.execute(f"select * from main.{BATCH_TABLE} order by month")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def check_contiguous(months):
    for previous, current in zip(months, months[1:]):
        if next_month(previous) != current:
            raise RuntimeError(
                f"Loaded months are not contiguous: {format_month(previous)} is followed "
                f"by {format_month(current)}. Run a full rebuild."
            )


def plan_incremental(loaded_months, environ=None):
    """Choose the batch month: the month after the last loaded one.

    Never skips ahead: batches load strictly in calendar order with no gaps.
    ``PIPELINE_BATCH_MONTH`` may name an already-loaded month (or the next
    one) to reprocess it explicitly. ``MAX_MONTH`` caps how far loading goes.
    Returns a RunPlan, or None with a reason when there is nothing to load.
    """
    environ = os.environ if environ is None else environ
    if not loaded_months:
        raise RuntimeError("The batch log is empty. Run a full rebuild first.")
    loaded_months = sorted(loaded_months)
    check_contiguous(loaded_months)
    following = next_month(loaded_months[-1])
    requested = environ.get("PIPELINE_BATCH_MONTH")
    if requested:
        batch = parse_month(requested)
        if batch < loaded_months[0] or batch > following:
            raise RuntimeError(
                f"PIPELINE_BATCH_MONTH={format_month(batch)} must be a loaded month "
                f"({format_month(loaded_months[0])} to {format_month(loaded_months[-1])}) "
                f"or the next month {format_month(following)}; months load without gaps."
            )
    else:
        batch = following
    cap = environ.get("MAX_MONTH")
    if cap and batch > parse_month(cap):
        return None, f"next month {format_month(batch)} is after MAX_MONTH={cap}"
    months = sorted(set(loaded_months) | {batch})
    return RunPlan("incremental", months, batch), None


# --------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------

@task(name="Validate raw source files", retries=2, retry_delay_seconds=10)
def download_raw_data():
    run([sys.executable, str(ROOT / "ingestion" / "download_data.py")])


@task(name="Check TLC for the next monthly file", retries=2, retry_delay_seconds=10)
def check_source_published(month):
    """True if the batch file is available (locally or at TLC); False if not yet published."""
    if (RAW / trip_filename(month)).is_file():
        print(f"{trip_filename(month)} is already in {RAW}; no availability check needed")
        return True
    url = download_data.trip_url(month)
    published = download_data.check_month_published(url)
    print(f"Availability of {url}: {'published' if published else 'not published yet (403/404)'}")
    return published


@task(name="Download and validate batch file", retries=2, retry_delay_seconds=10)
def download_batch(month):
    return download_data.download_month(month, RAW)


@task(name="Verify loaded source checksums")
def verify_loaded_sources(batch_log):
    """Every previously loaded file must still match its recorded SHA-256."""
    for row in batch_log:
        path = RAW / row["filename"]
        if not path.is_file():
            raise RuntimeError(f"Loaded source file is missing: {path}")
        if download_data.checksum(path) != row["sha256"]:
            raise RuntimeError(
                f"Unexpected source change for {row['filename']}: checksum does not match "
                "the batch log. Review the file before accepting a new source version."
            )
    print(f"Verified checksums of {len(batch_log)} loaded source files")


@task(name="Profile raw taxi data")
def profile_raw_data(month=None):
    command = [sys.executable, str(ROOT / "ingestion" / "profile_data.py")]
    if month is not None:
        command += ["--month", format_month(month)]
    run(command)


def prepare_candidate(copy_live):
    CANDIDATE.unlink(missing_ok=True)
    Path(str(CANDIDATE) + ".wal").unlink(missing_ok=True)
    if copy_live:
        if Path(str(WAREHOUSE) + ".wal").exists():
            raise RuntimeError(f"{WAREHOUSE}.wal exists; the live warehouse was not closed cleanly")
        shutil.copyfile(WAREHOUSE, CANDIDATE)


@task(name="Build and test candidate dbt models")
def build_dbt_models(plan=None):
    plan = plan or full_plan()
    executable = shutil.which("dbt")
    if executable is None:
        raise RuntimeError("The dbt executable was not found")
    command = [executable, "build", "--profiles-dir", ".", "--vars", json.dumps(plan.dbt_vars())]
    if plan.mode == "full":
        command.append("--full-refresh")
    run(
        command,
        TRANSFORMATIONS,
        {**os.environ, "DBT_WAREHOUSE_PATH": str(CANDIDATE),
         "DBT_ZONE_SOURCE": str(RAW / download_data.ZONE_FILENAME)},
    )
    record_batch_log(plan)


def record_batch_log(plan):
    """Write pipeline_batches in the candidate.

    Full mode recreates one row per month. Incremental mode upserts the batch
    row and refreshes accepted/rejected counts for every loaded file, because
    re-evaluation can move rows of earlier files between the two tables.
    """
    manifest = download_data.read_manifest(RAW / "source_manifest.json")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with duckdb.connect(str(CANDIDATE)) as connection:
        if plan.mode == "full":
            connection.execute(f"drop table if exists main.{BATCH_TABLE}")
        connection.execute(f"""
            create table if not exists main.{BATCH_TABLE} (
                month varchar primary key,
                filename varchar not null,
                source_url varchar not null,
                sha256 varchar not null,
                source_rows bigint not null,
                accepted_rows bigint not null,
                rejected_rows bigint not null,
                status varchar not null,
                load_mode varchar not null,
                processed_at_utc timestamp not null
            )
        """)
        new_months = plan.months if plan.mode == "full" else [plan.batch]
        for month in new_months:
            name = trip_filename(month)
            if name not in manifest:
                raise RuntimeError(f"{name} is not in the source manifest")
            details = manifest[name]
            connection.execute(f"delete from main.{BATCH_TABLE} where month = ?", [format_month(month)])
            connection.execute(
                f"insert into main.{BATCH_TABLE} values (?, ?, ?, ?, ?, 0, 0, 'loaded', ?, ?)",
                [format_month(month), name, details["source_url"], details["sha256"],
                 details["rows"], plan.mode, now],
            )
        connection.execute(f"""
            update main.{BATCH_TABLE} as b set
                accepted_rows = coalesce((select count(*) from main.fact_trips f
                                          where f.source_filename = b.filename), 0),
                rejected_rows = coalesce((select count(*) from main.rejected_trips r
                                          where r.source_filename = b.filename), 0)
        """)


@task(name="Validate candidate warehouse")
def validate_warehouse(plan=None):
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
        manifest = download_data.read_manifest(RAW / "source_manifest.json")
        batches = connection.execute(f"""
            select month, filename, sha256, source_rows, accepted_rows, rejected_rows
            from main.{BATCH_TABLE} order by month
        """).fetchall()
        months = [parse_month(row[0]) for row in batches]
        if not months:
            raise RuntimeError("The batch log is empty")
        check_contiguous(months)
        if plan is not None and months != plan.months:
            raise RuntimeError(
                f"Batch log months {[format_month(m) for m in months]} do not match "
                f"the planned months {[format_month(m) for m in plan.months]}"
            )
        accepted_by_file = dict(connection.execute(
            "select source_filename, count(*) from main.fact_trips group by 1"
        ).fetchall())
        rejected_by_file = dict(connection.execute(
            "select source_filename, count(*) from main.rejected_trips group by 1"
        ).fetchall())
        loaded_files = set()
        for month_text, filename, sha256, source_rows, accepted_log, rejected_log in batches:
            if filename != trip_filename(parse_month(month_text)):
                raise RuntimeError(f"Batch log file {filename} does not match month {month_text}")
            details = manifest.get(filename)
            if details is None:
                raise RuntimeError(f"{filename} is in the batch log but not in the source manifest")
            if details["sha256"] != sha256 or details["rows"] != source_rows:
                raise RuntimeError(f"Batch log and source manifest disagree for {filename}")
            good, bad = accepted_by_file.get(filename, 0), rejected_by_file.get(filename, 0)
            if source_rows != good + bad:
                raise RuntimeError(
                    f"Source count does not equal accepted plus rejected for {filename}: "
                    f"{source_rows} != {good} + {bad}"
                )
            if (good, bad) != (accepted_log, rejected_log):
                raise RuntimeError(f"Batch log counts are stale for {filename}")
            loaded_files.add(filename)
        stray = (set(accepted_by_file) | set(rejected_by_file)) - loaded_files
        if stray:
            raise RuntimeError(f"Warehouse rows come from files missing in the batch log: {sorted(stray)}")
        source = sum(row[3] for row in batches)
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
    return {"source_rows": source, "fact_rows": accepted, "rejected_rows": rejected,
            "daily_rows": daily, "months": f"{batches[0][0]} to {batches[-1][0]}"}


# Waits between attempts to replace the live warehouse (about two minutes in
# total). Measured on Docker Desktop for Windows: the Docker dashboard, idle or
# with an open read-only connection, does not block the replace; a Windows host
# process holding the file open does (PermissionError). A short-lived hold,
# e.g. a file scanner or a quick host query, is ridden out by these retries.
PUBLISH_RETRY_DELAYS = (2, 4, 8, 15, 30, 30, 30)


def publish_warehouse():
    # dbt's process and all validation readers are closed before replacement.
    with duckdb.connect(str(CANDIDATE)) as connection:
        connection.execute("checkpoint")
    if Path(str(CANDIDATE) + ".wal").exists():
        raise RuntimeError("Candidate WAL remains after checkpoint")
    # os.replace is atomic: each failed attempt leaves both the live warehouse
    # and the candidate exactly as they were.
    attempts = len(PUBLISH_RETRY_DELAYS) + 1
    for attempt in range(1, attempts + 1):
        try:
            os.replace(CANDIDATE, WAREHOUSE)
            if attempt > 1:
                print(f"Publication succeeded on attempt {attempt} of {attempts}")
            return
        except FileNotFoundError:
            raise
        except OSError as error:
            if attempt == attempts:
                raise RuntimeError(
                    f"Publication blocked: could not replace {WAREHOUSE} after {attempts} "
                    f"attempts ({error}). The live warehouse is unchanged and the tested "
                    f"candidate is kept at {CANDIDATE}. Close any Windows program that has "
                    "the warehouse file open (for example a dashboard or DuckDB client "
                    "started outside Docker), then run the pipeline again."
                ) from error
            delay = PUBLISH_RETRY_DELAYS[attempt - 1]
            print(f"Publication attempt {attempt} of {attempts} blocked ({error}); "
                  f"retrying in {delay} s")
            time.sleep(delay)


# --------------------------------------------------------------------------
# Flow
# --------------------------------------------------------------------------

def run_full(stages):
    plan = full_plan()
    print(f"Full rebuild of {format_month(plan.months[0])} to {format_month(plan.months[-1])}")
    with measured_stage(stages, "candidate_cleanup"):
        prepare_candidate(copy_live=False)
    with measured_stage(stages, "source_validation_ingestion"):
        download_raw_data()
    with measured_stage(stages, "profiling"):
        profile_raw_data()
    with measured_stage(stages, "dbt_build_and_tests"):
        build_dbt_models(plan)
    with measured_stage(stages, "candidate_validation"):
        result = validate_warehouse(plan)
    with measured_stage(stages, "publication"):
        publish_warehouse()
    print(f"Published warehouse: {result}")
    return result


def run_incremental(stages):
    with measured_stage(stages, "batch_planning"):
        batch_log = read_batch_log(WAREHOUSE)
        plan, reason = plan_incremental([parse_month(row["month"]) for row in batch_log])
    if plan is None:
        print(f"No new data: {reason}. The warehouse is unchanged.")
        return {"status": "no_new_data", "reason": reason}
    month = format_month(plan.batch)
    with measured_stage(stages, "source_check"):
        published = check_source_published(plan.batch)
    if not published:
        reason = f"{trip_filename(plan.batch)} is not published yet"
        print(f"No new data: {reason}. The warehouse is unchanged.")
        return {"status": "no_new_data", "reason": reason, "month": month}
    print(f"Incremental batch {month}; project period {plan.period_start} to {plan.period_end} (exclusive)")
    with measured_stage(stages, "source_validation_ingestion"):
        verify_loaded_sources([row for row in batch_log if row["month"] != month])
        download_batch(plan.batch)
    with measured_stage(stages, "profiling"):
        profile_raw_data(plan.batch)
    with measured_stage(stages, "candidate_copy"):
        prepare_candidate(copy_live=True)
    with measured_stage(stages, "dbt_build_and_tests"):
        build_dbt_models(plan)
    with measured_stage(stages, "candidate_validation"):
        result = validate_warehouse(plan)
    with measured_stage(stages, "publication"):
        publish_warehouse()
    result = {"status": "loaded", "month": month, **result}
    print(f"Published warehouse: {result}")
    return result


@flow(name="NYC Taxi End-to-End Pipeline", log_prints=True)
def nyc_taxi_pipeline(mode: Optional[str] = None):
    mode = (mode or os.environ.get("PIPELINE_MODE") or "full").strip().lower()
    if mode not in MODES:
        raise ValueError(f"PIPELINE_MODE must be one of {MODES}, got {mode!r}")
    timing_path = os.environ.get("PIPELINE_METRICS_PATH")
    started = time.perf_counter()
    timings = {"started_utc": datetime.now(timezone.utc).isoformat(), "mode": mode,
               "clock": "time.perf_counter", "stages_seconds": {}, "status": "failed"}
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    try:
        LOCK.mkdir()
    except FileExistsError as error:
        raise RuntimeError(
            f"Another run holds {LOCK}; remove it manually only after checking that run has stopped"
        ) from error
    try:
        if mode == "full":
            result = run_full(timings["stages_seconds"])
            timings["status"] = "success"
        else:
            result = run_incremental(timings["stages_seconds"])
            timings["status"] = "success" if result["status"] == "loaded" else result["status"]
        return result
    finally:
        timings["total_seconds"] = round(time.perf_counter() - started, 3)
        timings["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save_optional_timings(timing_path, timings)
        LOCK.rmdir()


if __name__ == "__main__":
    nyc_taxi_pipeline()
