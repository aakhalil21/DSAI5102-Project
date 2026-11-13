# Incremental monthly batch verification, 13 November 2026

This record covers the incremental monthly batch feature on real NYC TLC
data, run on the development machine (Windows 11, Docker Desktop). It does
not replace the October evidence (`summary.md`, `details.json`) or the
November benchmark. July and August 2025 are **not** part of the report's
analysis, which remains January–June 2025.

Machine-readable companion: `incremental-2026-11-13.json`. Raw outputs,
including the warehouse queries, the Prefect API export, logs and the
file-lock experiments, are under ignored
`data/verification/incremental-2026-11-13/`.

## What was tested

1. **July 2025, from the command line.** Starting from the published
   January–June warehouse, this command loaded July:
   `docker compose run --rm -e PIPELINE_MODE=incremental -e MAX_MONTH=2025-07 pipeline`
2. **August 2025, from the Prefect UI.** A **Quick run** of the
   `monthly-incremental-batches` deployment loaded August (flow run
   `mustard-beetle`).
3. **Evidence capture.** The January–August warehouse was then queried
   read-only.
4. **Full rebuild.** A default full January–June rebuild
   (`docker compose run --rm pipeline`) was run and checked against the
   submitted numbers.

## January–August warehouse after the two incremental runs

Every month reconciles: the manifest row count equals the batch-log
source count, which equals accepted plus rejected rows in the warehouse.
The batch-log accepted and rejected counts also equal the warehouse
counts, and each SHA-256 matches the source manifest.

| Month | Load mode | Source | Accepted | Rejected | Reconciles |
|---|---|---:|---:|---:|---|
| 2025-01 | full | 3,475,226 | 3,473,154 | 2,072 | Yes |
| 2025-02 | full | 3,577,543 | 3,572,379 | 5,164 | Yes |
| 2025-03 | full | 4,145,257 | 4,122,975 | 22,282 | Yes |
| 2025-04 | full | 3,970,553 | 3,935,784 | 34,769 | Yes |
| 2025-05 | full | 4,591,845 | 4,527,572 | 64,273 | Yes |
| 2025-06 | full | 4,322,960 | 4,254,377 | 68,583 | Yes |
| 2025-07 | incremental | 3,898,963 | 3,842,898 | 56,065 | Yes |
| 2025-08 | incremental | 3,574,091 | 3,526,256 | 47,835 | Yes |
| **Total** | | **31,556,438** | **31,255,395** | **301,043** | **Yes** |

Other checks on the same warehouse:

- No warehouse rows came from files missing from the batch log.
- Duplicate trip IDs across accepted and rejected: 0.
- 243 daily rows, 2025-01-01 to 2025-08-31.
- 29,421,180 financially eligible rows with $837,359,919.66 recorded
  charges. These figures are for this check only and are not report
  figures.
- The January–June counts above are identical to `summary.md`.
  Incremental loading did not change any earlier month.

Rejection reasons:

| File | invalid_timestamp_order | pickup_outside_project_period |
|---|---:|---:|
| 2025-07 | 56,064 | 1 (2009-01 pickup) |
| 2025-08 | 47,833 | 2 (one 2009-01, one 2025-09 pickup) |

**Period extension.** Loading July accepted **0** June-file rows with July
pickups. The raw June 2025 file contains no row with a pickup on or after
2025-07-01, and no June-file row with a July pickup is rejected either. On
this real data there was nothing to promote, so the June counts are
unchanged. The promotion mechanism itself is exercised by
`tests/synthetic_incremental_fixture.py`. The next real case is the single
August-file row with a September pickup. It stays rejected until September
is loaded.

Rows accepted from a neighbouring month's file are counted under that file:

- 6 June pickups in the July file
- 15 July pickups in the August file

These were classified with their own batch.

## Timings

These are single observations, not a controlled benchmark. Each one is
labelled with how it was measured.

| Run | Seconds | How measured | Downloads |
|---|---:|---|---|
| July incremental (CLI) | 429.943 | Host PowerShell `Measure-Command` | Includes the first download of July |
| August incremental (Prefect Quick run `mustard-beetle`) | 385.159 | Prefect flow run `total_run_time`; the UI showed 6 min 26 s | Includes the first download of August |
| Full January–June rebuild | 208.229 | Prefect log timestamps 16:41:53.160 to 16:45:21.389 UTC; excludes container start | None (files already local) |

The incremental runs include a first download and a copy of the whole live
warehouse to the candidate. The full rebuild had no downloads and no copy.
The figures are therefore not directly comparable.

For the full rebuild, the host timer and the optional timing JSON were not
captured. A shell math tool was missing and a path was mangled by Git Bash.
That is why its time comes from log timestamps.

August flow run `mustard-beetle`: COMPLETED, 16:26:33.575 to 16:32:58.735
UTC, parameter `mode=incremental`, 6 task runs, all COMPLETED:

| Task | Seconds |
|---|---:|
| Check TLC for the next monthly file | 0.511 |
| Verify loaded source checksums | 2.751 |
| Download and validate batch file | 6.098 |
| Profile raw taxi data | 1.960 |
| *(untracked: copy live warehouse to candidate)* | *115.905* |
| Build and test candidate dbt models | 253.925 |
| Validate candidate warehouse | 2.820 |

## Full January–June rebuild with the same code

These results match the submitted numbers exactly:

- 24,083,384 source rows = 23,886,241 accepted + 197,143 rejected.
- 22,560,818 financially eligible rows and $637,824,068.09 recorded
  charges.
- 181 daily rows, 2025-01-01 to 2025-06-30.
- Per-month source, accepted and rejected counts identical to `summary.md`.
- dbt `run_results.json`: 12 models succeeded and 43 tests passed.
- 36 Python unit tests passed. `tests/synthetic_fixture.py` and
  `tests/synthetic_incremental_fixture.py` passed.
- `pipeline_batches` was reset to January–June only.
  `source_manifest.json` still keeps the July and August entries.

## Schedule

- **Deployment:** `NYC Taxi End-to-End Pipeline/monthly-incremental-batches`.
- **Cron:** `0 6 2 * *` in UTC, which is 06:00 on the 2nd of each month.
  At capture, runs were queued for 2 Dec 2026, 2 Jan 2027 and 2 Feb 2027.
- **What a run loads:** at most the single next month after the last
  loaded month. If that file is not yet published (HTTP 403/404), the run
  ends successfully with "no new data" and changes nothing.

## Limitations

- **One month per run.** Catching up from 2025 to the latest published
  month takes one run per month.
- **Each run copies the whole warehouse.** About 5.3 GB for
  January–August, roughly 116 s of the August run. The dbt staging and
  reconciliation tests also scan every loaded file. Run time therefore grows
  with history.
- **Real-data equivalence not compared.** Incremental January–August was
  not compared row by row with a full January–August rebuild on real data.
  That equivalence is checked on synthetic data, after every batch, by
  `tests/synthetic_incremental_fixture.py`.
- **Dashboard file lock.** Tested the same day: the Docker dashboard
  service, idle or holding a read-only connection open, did not block
  publication. A Windows host program holding the file open does block it.
  Publication now retries for about two minutes, then fails safely with
  the live warehouse unchanged. A long-lived hold from a program outside
  Docker still needs that program to be closed.
