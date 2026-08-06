"""Apply the idempotent PostgreSQL schema used by the API."""

import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/minhdidauthe"


def main() -> None:
    database_url = os.getenv("URL_CSDL_POSTGRES", DEFAULT_URL)
    schema = (ROOT / "alembic" / "versions" / "0001_initial.sql").read_text(
        encoding="utf-8"
    )
    with psycopg.connect(database_url) as connection:
        connection.execute(schema)
    print("PostgreSQL schema applied successfully.")


if __name__ == "__main__":
    main()
