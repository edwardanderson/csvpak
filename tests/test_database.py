from __future__ import annotations

from pathlib import Path
import sqlite3

from csvpak.csvw import Column, Schema
from csvpak.database import create_table, export_csv, import_csv


def test_database_round_trip(tmp_path: Path) -> None:
    schema = Schema(
        columns=[
            Column(name="name", title="Name", datatype="string", required=True),
            Column(name="age", title="Age", datatype="integer"),
            Column(name="active", title="Active", datatype="boolean"),
        ]
    )

    csv_path = tmp_path / "input.csv"
    csv_path.write_text("name,age,active\nAlice,30,true\nBob,27,false\n", encoding="utf-8")

    db_path = tmp_path / "data.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        create_table(conn, schema)
        inserted = import_csv(conn, csv_path, schema)
    finally:
        conn.close()

    assert inserted == 2

    output_path = tmp_path / "output.csv"
    row_count = export_csv(db_path, output_path)

    assert row_count == 2
    assert output_path.read_text(encoding="utf-8").splitlines() == [
        "name,age,active",
        "Alice,30,1",
        "Bob,27,0",
    ]
