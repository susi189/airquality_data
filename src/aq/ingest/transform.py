METADATA_KEYS = {"count", "indices", "request"}


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
