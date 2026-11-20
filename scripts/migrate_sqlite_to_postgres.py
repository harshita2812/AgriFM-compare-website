import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, insert as postgres_insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.models import TABLES, metadata  # noqa: E402


JSON_COLUMNS = {
    table.name: {
        column.name
        for column in table.columns
        if isinstance(column.type.dialect_impl(postgresql.dialect()), JSONB)
    }
    for table in TABLES
}


def parse_value(table_name: str, column_name: str, value: Any) -> Any:
    if value is None:
        return None
    if column_name in JSON_COLUMNS[table_name] and isinstance(value, str):
        return json.loads(value)
    if column_name == "is_demo":
        return bool(value)
    if column_name in {"created_at", "completed_at", "fetched_at", "updated_at"} and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def migrate(source_path: Path, target_url: str) -> dict[str, int]:
    if target_url.startswith("postgres://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgres://"):]
    elif target_url.startswith("postgresql://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgresql://"):]
    if not target_url.startswith("postgresql+psycopg://"):
        raise ValueError("The target DATABASE_URL must use postgresql+psycopg://.")
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite source database not found: {source_path}")

    counts: dict[str, int] = {}
    with sqlite3.connect(f"file:{source_path.resolve().as_posix()}?mode=ro", uri=True) as source:
        source.row_factory = sqlite3.Row
        source_tables = {row["name"] for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        expected_tables = {table.name for table in TABLES}
        missing_tables = expected_tables - source_tables
        if missing_tables:
            raise ValueError(f"SQLite source is missing tables: {', '.join(sorted(missing_tables))}")

        target_engine = create_engine(target_url, pool_pre_ping=True)
        try:
            with target_engine.begin() as target:
                metadata.create_all(target, checkfirst=True)
                for table in TABLES:
                    rows = source.execute(f'SELECT * FROM "{table.name}"').fetchall()
                    counts[table.name] = len(rows)
                    if rows:
                        values = [
                            {
                                column.name: parse_value(table.name, column.name, row[column.name])
                                for column in table.columns
                            }
                            for row in rows
                        ]
                        statement = postgres_insert(table).values(values).on_conflict_do_nothing(
                            index_elements=[column.name for column in table.primary_key.columns]
                        )
                        target.execute(statement)

                for table in TABLES:
                    actual = target.execute(select(func.count()).select_from(table)).scalar_one()
                    if actual != counts[table.name]:
                        raise RuntimeError(
                            f"Row count mismatch for {table.name}: SQLite={counts[table.name]}, PostgreSQL={actual}."
                        )
        finally:
            target_engine.dispose()
    return counts


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Copy the AgriFM SQLite database into PostgreSQL.")
    parser.add_argument("--sqlite-path", type=Path, default=ROOT / "backend" / "agrifm.db")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Set DATABASE_URL to a PostgreSQL connection string or pass --database-url.")
    try:
        counts = migrate(args.sqlite_path, args.database_url)
    except Exception as error:
        print(
            f"Migration failed; no SQLite source data was changed, and any active target transaction was rolled back: {error}",
            file=sys.stderr,
        )
        return 1
    for table_name, count in counts.items():
        print(f"{table_name}: {count} rows verified")
    print(f"SQLite source retained at {args.sqlite_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
