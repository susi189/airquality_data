import argparse
import time
from datetime import date, timedelta

import httpx

from aq.ingest.fetch import fetch, fetch_measures, measures_path, save_json, save_raw
from aq.ingest.transform import transform_data, transform_measures

ENDPOINTS = ["components", "stations"]
# Pollutants with hourly data at most stations (checked against /measures/limits, Oct 2026)
MEASURE_COMPONENTS = {1: "PM10", 9: "PM2.5", 5: "NO2", 3: "O3", 4: "SO2"}
REQUEST_PAUSE_SECONDS = 0.5


def parse_args() -> argparse.Namespace:
    yesterday = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(description="Pull air quality data from the UBA API into data/raw.")
    parser.add_argument("--start", type=date.fromisoformat, default=yesterday, help="first day (YYYY-MM-DD)")
    parser.add_argument("--end", type=date.fromisoformat, default=yesterday, help="last day, inclusive (YYYY-MM-DD)")
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must not be after --end")
    return args


def ingest_metadata(client: httpx.Client) -> None:
    for endpoint in ENDPOINTS:
        try:
            data = fetch(client, endpoint)
            path = save_raw(data, endpoint)
            records = transform_data(data)
            print(f"{len(records)} records from {endpoint}, raw saved to {path}")
        except httpx.HTTPStatusError as e:
            print(f"The API returned an error for {endpoint}: {e}")
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {endpoint}: {e}")


def ingest_measures(client: httpx.Client, start: date, end: date) -> None:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    for component_id, name in MEASURE_COMPONENTS.items():
        for day in days:
            path = measures_path(component_id, day)
            if path.exists():
                print(f"{name} {day}: already saved, skipping")
                continue
            try:
                data = fetch_measures(client, component_id, day)
                save_json(data, path)
                records = transform_measures(data)
                print(f"{name} {day}: {len(records)} records, raw saved to {path}")
            except httpx.HTTPStatusError as e:
                print(f"The API returned an error for {name} {day}: {e}")
            except httpx.RequestError as e:
                print(f"An error occurred while requesting {name} {day}: {e}")
            time.sleep(REQUEST_PAUSE_SECONDS)


def main():
    args = parse_args()
    with httpx.Client(timeout=30) as client:
        ingest_metadata(client)
        ingest_measures(client, args.start, args.end)


if __name__ == "__main__":
    main()
