from datetime import date

import httpx

from aq.ingest.fetch import BASE_URL, fetch_measures, measures_path


def test_fetch_measures_requests_one_full_day_for_all_stations():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": {}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch_measures(client, component_id=5, day=date(2025, 9, 1))

    [request] = requests
    assert str(request.url).startswith(f"{BASE_URL}/measures/json?")
    assert dict(request.url.params) == {
        "date_from": "2025-09-01",
        "time_from": "1",
        "date_to": "2025-09-01",
        "time_to": "24",
        "component": "5",
        "scope": "2",
    }


def test_measures_path():
    assert measures_path(9, date(2025, 9, 1)).as_posix() == "data/raw/measures/9/2025-09-01.json"
