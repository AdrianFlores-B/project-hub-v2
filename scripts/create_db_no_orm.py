"""Create the application database with plain SQL, no ORM involved.

Counterpart of the SQLAlchemy/alembic setup: creates the target database
(default: projecthub_raw) on the compose postgres server and applies
scripts/schema.sql to it with asyncpg directly.

Usage:
    poetry run python scripts/create_db_no_orm.py [dbname]
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

SERVER_URL = os.environ.get(
    "POSTGRES_SERVER_URL", "postgresql://projecthub:projecthub@localhost:5432/postgres"
)


async def main() -> None:
    db_name = sys.argv[1] if len(sys.argv) > 1 else "projecthub_raw"
    schema_sql = (Path(__file__).parent / "schema.sql").read_text()

    conn = await asyncpg.connect(SERVER_URL)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if exists:
            print(f"database {db_name} already exists")
        else:
            # identifiers can't be query parameters, hence the format() -- the
            # name comes from the command line, not from user input
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"database {db_name} created")
    finally:
        await conn.close()

    conn = await asyncpg.connect(SERVER_URL.rsplit("/", 1)[0] + f"/{db_name}")
    try:
        await conn.execute(schema_sql)
        print("schema applied")
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        print("tables:", ", ".join(row["tablename"] for row in tables))
    except asyncpg.exceptions.DuplicateTableError:
        print("schema is already present in this database, nothing to do")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
