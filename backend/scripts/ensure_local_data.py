"""Idempotently prepare PostgreSQL schema and verified OSM/OSRM seed data."""

import os

import psycopg
from apply_schema import DEFAULT_URL
from apply_schema import main as apply_schema
from seed_postgres import main as seed_postgres


def main() -> None:
    apply_schema()
    database_url = os.getenv("URL_CSDL_POSTGRES", DEFAULT_URL)
    with psycopg.connect(database_url) as connection:
        count = connection.execute("SELECT count(*) FROM dia_diem").fetchone()[0]
    if count == 0:
        seed_postgres()
        print("Verified OSM/OSRM data seeded.")
    else:
        print(f"Verified catalogue already present ({count} places).")


if __name__ == "__main__":
    main()
