import httpx

from aq.ingest.fetch import fetch, save_raw
from aq.ingest.transform import transform_data

ENDPOINTS = ["components", "stations"]


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
