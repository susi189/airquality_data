from aq.ingest.transform import transform_data


def test_rows_at_top_level():
    response = {
        "count": 2,
        "indices": ["id", "code", "symbol"],
        "1": ["1", "PM10", "PM₁₀"],
        "2": ["5", "NO2", "NO₂"],
    }

    assert transform_data(response) == [
        {"id": "1", "code": "PM10", "symbol": "PM₁₀"},
        {"id": "5", "code": "NO2", "symbol": "NO₂"},
    ]


def test_rows_under_data_key():
    response = {
        "request": {"lang": "en"},
        "indices": ["id", "code"],
        "data": {"10": ["10", "DEBB021"]},
        "count": 1,
    }

    assert transform_data(response) == [{"id": "10", "code": "DEBB021"}]


def test_no_rows():
    assert transform_data({"count": 0, "indices": ["id"]}) == []
