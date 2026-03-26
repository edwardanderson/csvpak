from __future__ import annotations

import json
from pathlib import Path

from csvpak.csvw import parse_schema


def test_parse_schema_with_table_group(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "@context": "http://www.w3.org/ns/csvw",
                "tables": [
                    {
                        "url": "sample.csv",
                        "tableSchema": {
                            "columns": [
                                {"name": "name", "datatype": "string", "required": True},
                                {"name": "age", "datatype": "integer"},
                                {"name": "member", "datatype": "boolean"},
                            ],
                            "primaryKey": "name",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    schema = parse_schema(schema_path)

    assert schema.primary_key == ["name"]
    assert [column.name for column in schema.columns] == ["name", "age", "member"]
    assert schema.columns[0].required is True
    assert schema.columns[1].sqlite_type == "INTEGER"
    assert schema.columns[2].html_input_type == "checkbox"


def test_parse_schema_with_top_level_table_schema(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "@context": "http://www.w3.org/ns/csvw",
                "url": "sample.csv",
                "tableSchema": {
                    "columns": [
                        {"name": "id", "titles": ["Identifier"], "datatype": "string", "required": True},
                        {"name": "height_m", "titles": "Height", "datatype": "number"},
                    ],
                    "primaryKey": "id",
                },
            }
        ),
        encoding="utf-8",
    )

    schema = parse_schema(schema_path)

    assert schema.primary_key == ["id"]
    assert [column.name for column in schema.columns] == ["id", "height_m"]
    assert [column.title for column in schema.columns] == ["Identifier", "Height"]
    assert schema.columns[1].sqlite_type == "REAL"
