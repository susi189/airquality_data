import json
from datetime import date
from pathlib import Path

import httpx

from aq.config import RAW_DIR

BASE_URL = "https://luftdaten.umweltbundesamt.de/api/air-data/v3"


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
