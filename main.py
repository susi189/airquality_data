import httpx


BASE_URL = "https://luftdaten.umweltbundesamt.de/api/air-data/v3"
METADATA_KEYS = {"count", "indices", "request"}


def fetch(endpoint: str) -> dict:
    response = httpx.get(f"{BASE_URL}/{endpoint}", timeout=30)
    response.raise_for_status()
    return response.json()


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


def main(endpoint: str):
    try:
        records = transform_data(fetch(f"{endpoint}/json"))
        print(f"{len(records)} records from {endpoint}")
        print(records[0])
    except httpx.HTTPStatusError as e:
        print(f"The API returned an error: {e}")
    except httpx.RequestError as e:
        print(f"An error occurred while making the request: {e}")


if __name__ == "__main__":
    main("stations")  # Example endpoint, replace with the desired one