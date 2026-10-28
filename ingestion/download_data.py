from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

DATA_FILES = {
    "yellow_tripdata_2025-01.parquet": (
        "https://d37ci6vzurychx.cloudfront.net/"
        "trip-data/yellow_tripdata_2025-01.parquet"
    ),
    "taxi_zone_lookup.csv": (
        "https://d37ci6vzurychx.cloudfront.net/"
        "misc/taxi_zone_lookup.csv"
    ),
}


def download_file(url: str, destination: Path) -> None:
    """Download a file safely without overwriting an existing file."""

    if destination.exists() and destination.stat().st_size > 0:
        print(f"Skipping existing file: {destination.name}")
        return

    temporary_file = destination.with_suffix(
        destination.suffix + ".part"
    )

    print(f"Downloading {destination.name}...")

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(10, 120),
        ) as response:
            response.raise_for_status()

            with temporary_file.open("wb") as output_file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        output_file.write(chunk)

        temporary_file.replace(destination)

    except Exception:
        if temporary_file.exists():
            temporary_file.unlink()
        raise

    size_mb = destination.stat().st_size / (1024 * 1024)
    print(
        f"Downloaded {destination.name} "
        f"({size_mb:.2f} MB)"
    )


def main() -> None:
    """Download the initial project data files."""

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for filename, url in DATA_FILES.items():
        destination = RAW_DATA_DIR / filename
        download_file(url, destination)

    print("Initial data download completed successfully.")


if __name__ == "__main__":
    main()
