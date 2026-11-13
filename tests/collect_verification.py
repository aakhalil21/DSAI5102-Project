"""Persist a concise, auditable summary of the final Docker verification run.

The checked months come from the warehouse's pipeline_batches log, or from
PERIOD_START / PERIOD_END when the log is absent (default January-June 2025).
The output directory is required, so the submitted October evidence in
docs/verification/ is only rewritten when that path is passed explicitly.
"""

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

import sys

import duckdb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.download_data import (  # noqa: E402
    configured_period, format_month, month_range, next_month, parse_month, trip_filename,
)

RAW = ROOT / "data" / "raw"
WAREHOUSE = ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"
RESULTS = ROOT / "transformations" / "target" / "run_results.json"
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def loaded_months(db):
    """Months in the batch log, else the configured full-mode period."""
    exists = db.execute(
        "select count(*) from information_schema.tables "
        "where table_schema = 'main' and table_name = 'pipeline_batches'"
    ).fetchone()[0]
    if exists:
        months = [parse_month(row[0]) for row in db.execute(
            "select month from main.pipeline_batches order by month").fetchall()]
        if months:
            return months
    return month_range(*configured_period())


def expected_days(months):
    """Calendar-day count and first/last day of a contiguous month period."""
    first = date(*months[0], 1)
    last = date(*next_month(months[-1]), 1)
    return (last - first).days, str(first), str(date.fromordinal(last.toordinal() - 1))


def source_fingerprint():
    paths = [ROOT / "requirements.txt"]
    for folder in ("ingestion", "orchestration", "transformations", "dashboard", "tests", ".streamlit"):
        paths.extend(path for path in (ROOT / folder).rglob("*")
                     if path.is_file() and path.name != "collect_verification.py"
                     and path.suffix in {".py", ".sql", ".yml", ".yaml", ".toml"})
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--starting-commit", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--started-clean", action="store_true")
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Directory for summary.md and details.json. Pass docs/verification only "
             "to deliberately replace the submitted evidence.",
    )
    args = parser.parse_args()
    evidence = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    manifest = json.loads((RAW / "source_manifest.json").read_text(encoding="utf-8"))
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    dbt_counts = Counter()
    dbt_failures = []
    for result in results["results"]:
        kind = result["unique_id"].split(".", 1)[0]
        dbt_counts[f"{kind}_{result['status']}"] += 1
        if result["status"] not in {"success", "pass"}:
            dbt_failures.append({"id": result["unique_id"], "status": result["status"],
                                 "message": result.get("message", "")})
    assert dbt_counts["model_success"] == 12, dbt_counts
    assert dbt_counts["test_pass"] == 43, dbt_counts
    assert not dbt_failures, dbt_failures
    with duckdb.connect(str(WAREHOUSE), read_only=True) as db:
        accepted = dict(db.execute("""
            select source_filename, count(*) from main.fact_trips group by 1
        """).fetchall())
        rejected = dict(db.execute("""
            select source_filename, count(*) from main.rejected_trips group by 1
        """).fetchall())
        period = loaded_months(db)
        months = []
        for month in period:
            name = trip_filename(month)
            item = manifest[name]
            source = item["rows"]
            good, bad = accepted.get(name, 0), rejected.get(name, 0)
            assert source == good + bad, (name, source, good, bad)
            months.append({"month": format_month(month), "filename": name,
                           "source": source, "accepted": good, "rejected": bad,
                           "reconciled": True, "source_url": item["source_url"],
                           "size_bytes": item["size_bytes"], "sha256": item["sha256"]})
        total = {key: sum(row[key] for row in months)
                 for key in ("source", "accepted", "rejected")}
        assert total["source"] == total["accepted"] + total["rejected"]
        eligible, charges = db.execute("""
            select count(*), sum(total_amount) from main.fact_trips
            where not is_financial_adjustment and not is_financial_data_missing
        """).fetchone()
        day_count, first_day, last_day = db.execute("""
            select count(*), min(pickup_date), max(pickup_date)
            from main.mart_daily_performance
        """).fetchone()
        expected = expected_days(period)
        assert (day_count, str(first_day), str(last_day)) == expected, (day_count, first_day, last_day, expected)
        id_partition = db.execute("""
            select count(*) - count(distinct trip_id) from (
                select trip_id from main.fact_trips union all
                select trip_id from main.rejected_trips)
        """).fetchone()[0]
        assert id_partition == 0
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    details = {
        "timestamp_utc": timestamp, "starting_commit": args.starting_commit,
        "branch": args.branch, "starting_tree_clean": args.started_clean,
        "code_fingerprint_sha256": source_fingerprint(),
        "code_fingerprint_note": "Hash of relevant modified source and config files copied into the Docker image; starting commit alone does not identify the built tree.",
        "runtime": {"python": platform.python_version(),
                    **{name: version(name) for name in ("dbt-core", "dbt-duckdb", "duckdb", "streamlit", "prefect", "pyarrow")}},
        "sources": months, "taxi_zone_source": manifest["taxi_zone_lookup.csv"],
        "totals": total,
        "reconciliation": f"all {NUMBER_WORDS.get(len(months), len(months))} files and total reconcile exactly",
        "dbt": {"generated_at": results["metadata"].get("generated_at"),
                "counts": dict(dbt_counts), "failures": dbt_failures},
        "warehouse": {"eligible_rows": eligible, "eligible_recorded_charges": charges,
                      "daily_rows": day_count, "first_day": str(first_day),
                      "last_day": str(last_day), "duplicate_trip_ids": id_partition},
    }
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "details.json").write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
    lines = ["# Final verification evidence", "", f"Generated UTC: {timestamp}",
             f"Branch: `{args.branch}`", f"Starting commit: `{args.starting_commit}`",
             f"Starting tree clean: {args.started_clean}",
             f"Modified-tree source fingerprint (SHA-256): `{details['code_fingerprint_sha256']}`",
             "", "| Month | Source | Accepted | Rejected | Reconciles |",
             "|---|---:|---:|---:|---|"]
    for row in months:
        lines.append(f"| {row['month']} | {row['source']:,} | {row['accepted']:,} | {row['rejected']:,} | Yes |")
    lines += [f"| **Total** | **{total['source']:,}** | **{total['accepted']:,}** | **{total['rejected']:,}** | **Yes** |",
              "", "## Checks", "", "- dbt: 12 model builds and 43 data tests passed; no dbt failures or skips.",
              f"- Warehouse: {eligible:,} eligible rows, ${charges:,.2f} recorded charges; {day_count} daily rows from {first_day} through {last_day}; no duplicate trip IDs.",
              "- Source URLs, byte sizes, SHA-256 hashes, runtime versions, and dbt generation timestamp are in `details.json`.",
              "- Full pipeline log and raw dbt artifacts are retained under ignored `data/verification/`.",
              "- Focused Python, synthetic fixture, warehouse verification, dashboard health, and browser results are recorded separately when run.", ""]
    (evidence / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {evidence / 'summary.md'} and {evidence / 'details.json'}")


if __name__ == "__main__":
    main()
