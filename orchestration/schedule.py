"""Serve the pipeline on a monthly cron schedule in incremental mode.

Each scheduled run checks TLC for the single next monthly file and loads it
if it has been published; otherwise it logs "no new data" and succeeds
without changing the warehouse. Settings:

* PIPELINE_SCHEDULE_CRON  cron expression (default "0 6 2 * *": 06:00 on the 2nd)
* PIPELINE_SCHEDULE_TZ    time zone for the cron (default "UTC")
* MAX_MONTH               optional YYYY-MM cap on loading
* PREFECT_API_URL         optional existing Prefect server. Without it a local
                          Prefect server is started in this process's
                          container: Prefect 2's ephemeral API does not run
                          the scheduler service, so cron runs would never be
                          created.
"""

import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CRON = "0 6 2 * *"
LOCAL_PORT = 4200


def start_local_server(timeout_seconds=180):
    """Start `prefect server start` and point this process at it.

    The server binds to PREFECT_SERVER_API_HOST (default 127.0.0.1; the
    Compose service sets 0.0.0.0 so the UI is reachable through the published
    port). This process always talks to it over 127.0.0.1.
    """
    host = os.environ.get("PREFECT_SERVER_API_HOST") or "127.0.0.1"
    server = subprocess.Popen(
        ["prefect", "server", "start", "--host", host, "--port", str(LOCAL_PORT)]
    )
    url = f"http://127.0.0.1:{LOCAL_PORT}/api"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"The local Prefect server exited with code {server.returncode}")
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=5):
                break
        except (urllib.error.URLError, OSError):
            time.sleep(2)
    else:
        server.terminate()
        raise RuntimeError("The local Prefect server did not become healthy in time")
    os.environ["PREFECT_API_URL"] = url
    print(f"Started local Prefect server at {url}")
    return server


def main():
    server = None if os.environ.get("PREFECT_API_URL") else start_local_server()
    # Import Prefect only after PREFECT_API_URL is final.
    from prefect.client.schemas.schedules import CronSchedule

    from orchestration.pipeline import nyc_taxi_pipeline

    cron = os.environ.get("PIPELINE_SCHEDULE_CRON") or DEFAULT_CRON
    timezone = os.environ.get("PIPELINE_SCHEDULE_TZ") or "UTC"
    print(f"Serving monthly incremental batches on cron '{cron}' ({timezone})")
    try:
        nyc_taxi_pipeline.serve(
            name="monthly-incremental-batches",
            schedule=CronSchedule(cron=cron, timezone=timezone),
            parameters={"mode": "incremental"},
            description="Load the next published monthly TLC file, if any.",
        )
    finally:
        if server is not None:
            server.terminate()


if __name__ == "__main__":
    main()
