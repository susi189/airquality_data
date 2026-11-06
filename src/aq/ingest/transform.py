METADATA_KEYS = {"count", "indices", "request", "meta"}


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


def transform_measures(response: dict) -> list[dict]:
    # Measures are nested: data -> station id -> date start -> [component id, scope id, value, date end, index]
    fields = response["indices"]["data"]["station id"]["date start"]

    transformed_data = []
    for station_id, hours in response["data"].items():
        for date_start, values in hours.items():
            record = {"station id": station_id, "date start": date_start}
            for i, element in enumerate(values):
                record[fields[i]] = element
            transformed_data.append(record)
    return transformed_data
