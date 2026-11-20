from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import Boolean, DateTime, Engine, bindparam, create_engine, event, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection, Row
from sqlalchemy.pool import NullPool

from apps.api.models import metadata


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _database_url() -> str:
    sqlite_path = os.environ.get("AGRIFM_DB_PATH")
    if sqlite_path:
        path = Path(sqlite_path)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"

    url = os.environ.get("DATABASE_URL", "sqlite:///backend/agrifm.db")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        path = Path(url[len("sqlite:///"):])
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    return url


DATABASE_URL = _database_url()
engine: Engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool if DATABASE_URL.startswith("sqlite") else None,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    schema = os.environ.get("AGRIFM_DB_SCHEMA")
    if schema:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
            raise ValueError("AGRIFM_DB_SCHEMA must be a simple PostgreSQL schema name.")

        @event.listens_for(engine, "connect")
        def _set_postgres_schema(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute(f'SET search_path TO "{schema}"')
            cursor.close()


def column_names(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


class CompatibleRow(Mapping[str, Any]):
    def __init__(self, row: Row[Any]):
        self._mapping = row._mapping

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return tuple(self._mapping.values())[key]
        value = self._mapping[key]
        if key.endswith("_json") or key == "model_ids":
            if isinstance(value, (dict, list)):
                return json.dumps(value)
        return value

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self) -> int:
        return len(self._mapping)


class CompatibleResult:
    def __init__(self, result: Any):
        self._result = result
        self.rowcount = result.rowcount

    def fetchone(self) -> CompatibleRow | None:
        row = self._result.fetchone()
        return CompatibleRow(row) if row is not None else None

    def fetchall(self) -> list[CompatibleRow]:
        return [CompatibleRow(row) for row in self._result.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


def _split_sql_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",")]


def _parameter_columns(statement: str, count: int) -> dict[int, tuple[str, str]]:
    insert = re.search(
        r"INSERT\s+INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)",
        statement,
        re.IGNORECASE | re.DOTALL,
    )
    if insert:
        table_name, columns_sql, values_sql = insert.groups()
        result: dict[int, tuple[str, str]] = {}
        position = 0
        for column_name, value_sql in zip(_split_sql_list(columns_sql), _split_sql_list(values_sql)):
            placeholders = value_sql.count("?")
            if value_sql.strip() == "?":
                result[position] = (table_name, column_name.strip('"`'))
            position += placeholders
        return result

    update = re.search(r"UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\s+|$)", statement, re.IGNORECASE | re.DOTALL)
    if update:
        table_name, assignments = update.groups()
        result = {}
        position = 0
        for assignment in _split_sql_list(assignments):
            match = re.match(r'\s*["`]?(\w+)["`]?\s*=\s*\?\s*$', assignment)
            placeholders = assignment.count("?")
            if match:
                result[position] = (table_name, match.group(1))
            position += placeholders
        return result
    return {}


class DatabaseConnection:
    def __init__(self, connection: Connection):
        self._connection = connection

    def execute(self, statement: str, parameters: tuple[Any, ...] | list[Any] = ()) -> CompatibleResult:
        if isinstance(parameters, Mapping):
            return CompatibleResult(self._connection.execute(text(statement), parameters))

        parameter_columns = _parameter_columns(statement, len(parameters))
        names: list[str] = []

        def replace_placeholder(_match: re.Match[str]) -> str:
            name = f"p{len(names)}"
            names.append(name)
            return f":{name}"

        compiled_statement = re.sub(r"\?", replace_placeholder, statement)
        if self._connection.dialect.name == "postgresql":
            compiled_statement = re.sub(r"\bis_demo\s*=\s*1\b", "is_demo = TRUE", compiled_statement, flags=re.IGNORECASE)

        values = {name: value for name, value in zip(names, parameters)}
        bind_types = []
        for position, name in enumerate(names):
            target = parameter_columns.get(position)
            if not target:
                continue
            table_name, column_name = target
            column = metadata.tables.get(table_name)
            if column is None or column_name not in column.c:
                continue
            column_type = column.c[column_name].type.dialect_impl(self._connection.dialect)
            value = values[name]
            if self._connection.dialect.name == "postgresql" and isinstance(column_type, JSONB):
                if isinstance(value, str):
                    values[name] = json.loads(value)
                bind_types.append(bindparam(name, type_=column_type))
            elif isinstance(column_type, DateTime) and isinstance(value, str):
                values[name] = datetime.fromisoformat(value)
                bind_types.append(bindparam(name, type_=column_type))
            elif isinstance(column_type, Boolean) and value in (0, 1):
                values[name] = bool(value)
                bind_types.append(bindparam(name, type_=column_type))

        query = text(compiled_statement)
        if bind_types:
            query = query.bindparams(*bind_types)
        return CompatibleResult(self._connection.execute(query, values))

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def connect() -> DatabaseConnection:
    return DatabaseConnection(engine.connect())


def migrate_legacy_schema() -> None:
    with closing(connect()) as conn:
        for table_name in ("models", "regions", "datasets", "runs"):
            columns = column_names(table_name)
            if "is_demo" not in columns:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT TRUE")
        if "provenance_json" not in column_names("runs"):
            provenance_type = "JSONB" if engine.dialect.name == "postgresql" else "TEXT"
            conn.execute(f"ALTER TABLE runs ADD COLUMN provenance_json {provenance_type}")
        conn.commit()
