# Verification package

`summary.md` and `details.json` are generated from the published warehouse,
the raw source manifest, and the persisted dbt `run_results.json`. The
starting Git commit identifies the pre-change baseline. The source
fingerprint identifies the modified source tree tested in Docker; it does
not claim that the unchanged starting commit produced these results.

The generated files under `data/verification/` stay local and are ignored
by Git. They include the full pipeline log, dbt `target` and `logs`, and
captured output from the focused Python tests, synthetic fixture, warehouse
verification, and dashboard health check. Share them with the small summary
when an independent reviewer needs the complete logs.

`browser_review.md` records the later desktop and 400 px browser checks,
the dashboard-only correction, its separate source fingerprint, and the
locations of screenshots under `data/verification/screenshots/`.

Commands for the final run (PowerShell from the repository root):

```powershell
docker compose build pipeline dashboard
docker compose run --rm pipeline python tests/synthetic_fixture.py
docker compose stop dashboard
docker compose run --rm pipeline
docker compose run --rm pipeline python -m unittest discover -s tests -p "test_*.py"
docker compose run --rm pipeline python tests/verify_warehouse.py
docker compose run --rm pipeline python tests/collect_verification.py --starting-commit ce9d05adfd944468a38a4658fc07dc40fcae892d --branch fix/final-verification --started-clean
docker compose up -d dashboard
docker compose exec -T dashboard python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8501/_stcore/health').read().decode())"
```

The actual command outputs and warnings are captured in the run's local
logs. A successful health response establishes that Streamlit is serving;
it does not establish that every chart or interaction works.

## November 2026 controlled rebuild

`benchmark-2026-11-07.md` and `benchmark-2026-11-07.json` are a separate
performance record for the revision that is now merged into `main` (it was
measured on a feature branch before the merge). They do not replace
`summary.md` or `details.json`, which document the earlier October revision.
The detailed logs, timing JSON and five-second Docker memory samples are
under ignored `data/verification/benchmark-2026-11-07/`.

From the repository root, after checking Docker capacity and building the
images, the measured command is:

```powershell
docker compose build pipeline dashboard
python tests/benchmark_pipeline.py --output data/verification/benchmark-2026-11-07
```

The utility stops the dashboard before the candidate can be published,
passes an opt-in timing path to the pipeline, and records host command time
with a monotonic clock. Stage timings are also monotonic and are saved by
the pipeline. Its monitor samples `docker stats` every five seconds; that is
container usage, not process memory or a guaranteed peak. The script leaves
the dashboard stopped so that post-run verification can finish before
`docker compose up -d dashboard`.

## Incremental batch checks (added later)

These commands check the incremental monthly batch feature. They are not
part of the October or November evidence above and do not rewrite it.
`tests/synthetic_incremental_fixture.py` uses only synthetic files in a
temporary folder. It never downloads data and never touches the real
warehouse, raw files or dbt artifacts.

```powershell
docker compose run --rm pipeline python tests/synthetic_incremental_fixture.py
docker compose run --rm pipeline python -m unittest discover -s tests -p "test_*.py"
```

To confirm that a full rebuild still matches `summary.md`, follow
"Confirm a full rebuild still matches the submitted numbers" in the
project README.

`tests/collect_verification.py` now needs `--output-dir`, so it never
overwrites the October `summary.md` and `details.json` by accident. The
historical command above predates this option. It checks the months in
the warehouse's `pipeline_batches` log, or `PERIOD_START`/`PERIOD_END`
when that log is absent. For the default January-June period its
assertions are unchanged: six files, 181 days, 12 models and 43 tests.
Example:

```powershell
docker compose run --rm pipeline python tests/collect_verification.py --starting-commit <commit> --branch <branch> --output-dir data/verification/collected
```

`incremental-2026-11-13.md` and its JSON companion record the real-data
verification of the incremental feature: July and August 2025 loaded
incrementally, then a full January-June rebuild. They also record the
timings as measured and the dashboard file-lock findings. The raw outputs
are under ignored `data/verification/incremental-2026-11-13/`.
