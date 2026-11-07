"""Run one measured Docker rebuild; keep monitoring outside pipeline logic."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
NAME = "taxi-benchmark-pipeline"
UNITS = {"b": 1, "kib": 1024, "mib": 1024**2, "gib": 1024**3,
         "kb": 1000, "mb": 1000**2, "gb": 1000**3}


def memory_bytes(value):
    match = re.fullmatch(r"\s*([\d.]+)\s*([A-Za-z]+)\s*", value)
    if not match:
        raise ValueError(value)
    return int(float(match.group(1)) * UNITS[match.group(2).lower()])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Ignored data/verification subdirectory")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to((ROOT / "data" / "verification").resolve()):
        parser.error("--output must be under data/verification")
    output.mkdir(parents=True, exist_ok=True)

    with (output / "dashboard-stop.log").open("w", encoding="utf-8") as log:
        subprocess.run(["docker", "compose", "stop", "dashboard"], cwd=ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True)

    command = ["docker", "compose", "run", "--rm", "--name", NAME,
               "-e", f"PIPELINE_METRICS_PATH=/app/data/verification/{output.name}/pipeline_timings.json",
               "pipeline"]
    observations = []
    errors = []
    stop = threading.Event()

    def sample():
        while not stop.wait(5):
            try:
                result = subprocess.run(
                    ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", NAME],
                    capture_output=True, text=True, timeout=15, check=True)
                usage = result.stdout.strip().split("/")[0]
                observations.append({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                     "container_memory_bytes": memory_bytes(usage)})
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                errors.append(str(error))

    started_utc = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    with (output / "pipeline.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        monitor = threading.Thread(target=sample, daemon=True)
        monitor.start()
        try:
            returncode = process.wait()
        finally:
            stop.set()
            monitor.join(timeout=20)
    report = {
        "started_utc": started_utc,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "host_command_seconds": round(time.perf_counter() - started, 3),
        "clock": "time.perf_counter",
        "returncode": returncode,
        "memory_sampling": {
            "scope": "Docker container usage reported by docker stats; not process memory or a guaranteed peak",
            "nominal_interval_seconds": 5,
            "observations": observations,
            "observed_sampled_max_bytes": max((x["container_memory_bytes"] for x in observations), default=None),
            "errors": errors[-5:],
        },
    }
    (output / "host_measurements.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Pipeline exit={returncode}; host command={report['host_command_seconds']}s; "
          f"memory samples={len(observations)}; output={output}")
    raise SystemExit(returncode)


if __name__ == "__main__":
    main()
