import duckdb

from aq.config import DUCKDB_PATH, RAW_DIR
from aq.load.loader import load_all


def main():
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DUCKDB_PATH)) as con:
        counts = load_all(con, RAW_DIR)
    for table, rows in counts.items():
        print(f"raw.{table}: {rows} rows")
    print(f"Loaded into {DUCKDB_PATH}")


if __name__ == "__main__":
    main()
