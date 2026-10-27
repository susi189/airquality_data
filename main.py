import json
from datetime import date
from pathlib import Path

import httpx


BASE_URL = "https://luftdaten.umweltbundesamt.de/api/air-data/v3"
METADATA_KEYS = {"count", "indices", "request"}
RAW_DIR = Path("data/raw")
ENDPOINTS = ["components", "stations"]


def fetch(endpoint: str) -> dict:
    response = httpx.get(f"{BASE_URL}/{endpoint}/json", timeout=30)
    response.raise_for_status()
    return response.json()


def save_raw(data: dict, endpoint: str) -> Path:
    folder = RAW_DIR / endpoint
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{date.today().isoformat()}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def transform_data(response: dict) -> list[dict]:
    fields = response["indices"]
    rows = response.get("data", response)

    transformed_data = []
    for key, value in rows.items():
        if key in METADATA_KEYS:
            continue
        record = {}
        for i, element in enumerate(value):
            record[fields[i]] = element
        transformed_data.append(record)
    return transformed_data


def main():
    for endpoint in ENDPOINTS:
        try:
            data = fetch(endpoint)
            path = save_raw(data, endpoint)
            records = transform_data(data)
            print(f"{len(records)} records from {endpoint}, raw saved to {path}")
            print(records[0])
        except httpx.HTTPStatusError as e:
            print(f"The API returned an error for {endpoint}: {e}")
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {endpoint}: {e}")


if __name__ == "__main__":
    main()
