import json
from datetime import date
from pathlib import Path

import httpx

from aq.config import RAW_DIR

BASE_URL = "https://luftdaten.umweltbundesamt.de/api/air-data/v4"
HOURLY_SCOPE = 2  # "1SMW": one hour average


def fetch(client: httpx.Client, endpoint: str, params: dict | None = None) -> dict:
    response = client.get(f"{BASE_URL}/{endpoint}/json", params=params)
    response.raise_for_status()
    return response.json()


def fetch_measures(client: httpx.Client, component_id: int, day: date) -> dict:
    # Hours run 1-24 and mark the end of the hour: 1 = 00:00-01:00, 24 = 23:00-24:00.
    # Leaving out `station` returns all stations in one response.
    params = {
        "date_from": day.isoformat(),
        "time_from": 1,
        "date_to": day.isoformat(),
        "time_to": 24,
        "component": component_id,
        "scope": HOURLY_SCOPE,
    }
    return fetch(client, "measures", params)


def measures_path(component_id: int, day: date) -> Path:
    return RAW_DIR / "measures" / str(component_id) / f"{day.isoformat()}.json"


def save_json(data: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def save_raw(data: dict, endpoint: str) -> Path:
    return save_json(data, RAW_DIR / endpoint / f"{date.today().isoformat()}.json")
