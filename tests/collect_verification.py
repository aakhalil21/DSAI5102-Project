"""Persist a concise, auditable summary of the final Docker verification run."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

import duckdb


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
WAREHOUSE = ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"
RESULTS = ROOT / "transformations" / "target" / "run_results.json"
EVIDENCE = ROOT / "docs" / "verification"


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
    args = parser.parse_args()
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
        months = []
        for month in range(1, 7):
            name = f"yellow_tripdata_2025-{month:02d}.parquet"
            item = manifest[name]
            source = item["rows"]
            good, bad = accepted.get(name, 0), rejected.get(name, 0)
            assert source == good + bad, (name, source, good, bad)
            months.append({"month": f"2025-{month:02d}", "filename": name,
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
        assert day_count == 181 and str(first_day) == "2025-01-01" and str(last_day) == "2025-06-30"
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
        "totals": total, "reconciliation": "all six files and total reconcile exactly",
        "dbt": {"generated_at": results["metadata"].get("generated_at"),
                "counts": dict(dbt_counts), "failures": dbt_failures},
        "warehouse": {"eligible_rows": eligible, "eligible_recorded_charges": charges,
                      "daily_rows": day_count, "first_day": str(first_day),
                      "last_day": str(last_day), "duplicate_trip_ids": id_partition},
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "details.json").write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
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
    (EVIDENCE / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {EVIDENCE / 'summary.md'} and {EVIDENCE / 'details.json'}")


if __name__ == "__main__":
    main()
