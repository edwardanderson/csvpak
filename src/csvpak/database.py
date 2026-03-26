from __future__ import annotations

import csv
from pathlib import Path
import sqlite3

from .csvw import Column, Schema


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sql_literal(value: str | int | float | bool | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _convert_value(value: str | None, column: Column) -> str | int | float | None:
    if value is None:
        return None

    stripped = value.strip()
    if stripped == "":
        return None

    if column.datatype == "integer":
        return int(stripped)
    if column.datatype == "number":
        return float(stripped)
    if column.datatype == "boolean":
        if stripped.lower() in {"1", "true", "yes", "y"}:
            return 1
        if stripped.lower() in {"0", "false", "no", "n"}:
            return 0
        raise ValueError(f"Cannot parse boolean value '{value}' for column '{column.name}'")

    return stripped


def create_table(conn: sqlite3.Connection, schema: Schema) -> None:
    has_primary_key = bool(schema.primary_key)
    column_definitions: list[str] = []

    if not has_primary_key:
        column_definitions.append('"_id" INTEGER PRIMARY KEY AUTOINCREMENT')

    for column in schema.columns:
        parts = [
            _quote_identifier(column.name),
            column.sqlite_type,
        ]
        if column.required:
            parts.append("NOT NULL")
        if column.default is not None:
            parts.append(f"DEFAULT {_sql_literal(column.default)}")
        if column.name in schema.primary_key:
            parts.append("PRIMARY KEY")
        column_definitions.append(" ".join(parts))

    create_sql = "CREATE TABLE data (" + ", ".join(column_definitions) + ")"
    conn.execute(create_sql)


def import_csv(conn: sqlite3.Connection, csv_path: Path, schema: Schema) -> int:
    columns = schema.columns
    column_names = [column.name for column in columns]

    placeholders = ", ".join("?" for _ in columns)
    insert_sql = (
        f"INSERT INTO data ({', '.join(_quote_identifier(name) for name in column_names)}) "
        f"VALUES ({placeholders})"
    )

    inserted = 0
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV file is missing a header row")

        missing = [name for name in column_names if name not in reader.fieldnames]
        if missing:
            missing_names = ", ".join(missing)
            raise ValueError(f"CSV file is missing expected columns: {missing_names}")

        rows_to_insert: list[tuple[str | int | float | None, ...]] = []
        for raw_row in reader:
            converted = tuple(_convert_value(raw_row.get(column.name), column) for column in columns)
            rows_to_insert.append(converted)

        if rows_to_insert:
            conn.executemany(insert_sql, rows_to_insert)
            inserted = len(rows_to_insert)

    conn.commit()
    return inserted


def export_csv(db_path: Path, output_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        pragma_rows = conn.execute("PRAGMA table_info(data)").fetchall()
        column_names = [row[1] for row in pragma_rows if row[1] != "_id"]

        if not column_names:
            raise ValueError("No exportable columns found in table 'data'")

        select_sql = "SELECT " + ", ".join(_quote_identifier(name) for name in column_names) + " FROM data"
        rows = conn.execute(select_sql).fetchall()
    finally:
        conn.close()

    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(column_names)
        writer.writerows(rows)

    return len(rows)


def count_csv_rows(csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return sum(1 for _ in reader)
