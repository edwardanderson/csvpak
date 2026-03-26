from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from csvw import TableGroup

SUPPORTED_DATATYPES = {
    "string",
    "integer",
    "number",
    "boolean",
    "date",
    "datetime",
}

SQLITE_TYPES = {
    "string": "TEXT",
    "integer": "INTEGER",
    "number": "REAL",
    "boolean": "INTEGER",
    "date": "TEXT",
    "datetime": "TEXT",
}

HTML_INPUT_TYPES = {
    "string": "text",
    "integer": "number",
    "number": "number",
    "boolean": "checkbox",
    "date": "date",
    "datetime": "datetime-local",
}


@dataclass(slots=True)
class Column:
    name: str
    title: str
    datatype: str = "string"
    required: bool = False
    default: str | int | float | bool | None = None
    enum_values: list[str] = field(default_factory=list)

    @property
    def sqlite_type(self) -> str:
        return SQLITE_TYPES[self.datatype]

    @property
    def html_input_type(self) -> str:
        return HTML_INPUT_TYPES[self.datatype]


@dataclass(slots=True)
class Schema:
    columns: list[Column]
    primary_key: list[str] = field(default_factory=list)


def _normalise_datatype(raw_datatype: object) -> str:
    if raw_datatype is None:
        return "string"

    if hasattr(raw_datatype, "base"):
        datatype = str(getattr(raw_datatype, "base"))
    elif isinstance(raw_datatype, str):
        datatype = raw_datatype
    elif isinstance(raw_datatype, dict):
        datatype = str(raw_datatype.get("base") or raw_datatype.get("@id") or "string")
    else:
        datatype = "string"

    datatype = datatype.lower().strip()
    if datatype not in SUPPORTED_DATATYPES:
        raise ValueError(f"Unsupported CSVW datatype: {datatype}")
    return datatype


def _parse_primary_key(raw_primary_key: object) -> list[str]:
    if raw_primary_key is None:
        return []
    if isinstance(raw_primary_key, str):
        return [raw_primary_key]
    if isinstance(raw_primary_key, list):
        return [str(value) for value in raw_primary_key]
    raise ValueError("CSVW primaryKey must be a string or list of strings")


def _extract_raw_columns(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("tableSchema"), dict):
        columns = payload["tableSchema"].get("columns")
        if isinstance(columns, list):
            return [item for item in columns if isinstance(item, dict)]

    tables = payload.get("tables")
    if isinstance(tables, list) and tables and isinstance(tables[0], dict):
        table_schema = tables[0].get("tableSchema")
        if isinstance(table_schema, dict):
            columns = table_schema.get("columns")
            if isinstance(columns, list):
                return [item for item in columns if isinstance(item, dict)]

    return []


def _parse_schema_from_payload(payload: dict[str, object]) -> Schema:
    table_schema = payload.get("tableSchema")
    if not isinstance(table_schema, dict):
        tables = payload.get("tables")
        if isinstance(tables, list) and tables and isinstance(tables[0], dict):
            table_schema = tables[0].get("tableSchema")

    if not isinstance(table_schema, dict):
        raise ValueError("CSVW schema must define at least one table")

    raw_columns = table_schema.get("columns")
    if not isinstance(raw_columns, list) or not raw_columns:
        raise ValueError("CSVW schema must contain tableSchema.columns")

    columns: list[Column] = []
    for raw_column in raw_columns:
        if not isinstance(raw_column, dict):
            continue

        name = raw_column.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Each CSVW column must define a non-empty name")

        title = raw_column.get("titles")
        if isinstance(title, list) and title:
            title_value = str(title[0])
        elif isinstance(title, str) and title:
            title_value = title
        else:
            title_value = name

        constraints = raw_column.get("constraints")
        enum_values: list[str] = []
        if isinstance(constraints, dict):
            enum = constraints.get("enum")
            if isinstance(enum, list):
                enum_values = [str(item) for item in enum]

        default = raw_column.get("default")
        if default == "":
            default = None

        columns.append(
            Column(
                name=name,
                title=title_value,
                datatype=_normalise_datatype(raw_column.get("datatype")),
                required=bool(raw_column.get("required")),
                default=default,
                enum_values=enum_values,
            )
        )

    return Schema(columns=columns, primary_key=_parse_primary_key(table_schema.get("primaryKey")))


def parse_schema(path: Path) -> Schema:
    payload = json.loads(path.read_text(encoding="utf-8"))
    table_group = TableGroup.from_file(path)
    if not table_group.tables:
        return _parse_schema_from_payload(payload)

    table = table_group.tables[0]
    table_schema = table.tableSchema
    if table_schema is None or not table_schema.columns:
        raise ValueError("CSVW schema must contain tableSchema.columns")

    raw_columns = _extract_raw_columns(path)
    enums_by_name: dict[str, list[str]] = {}
    for raw_column in raw_columns:
        name = raw_column.get("name")
        constraints = raw_column.get("constraints")
        if not isinstance(name, str) or not isinstance(constraints, dict):
            continue
        enum_values = constraints.get("enum")
        if isinstance(enum_values, list):
            enums_by_name[name] = [str(item) for item in enum_values]

    columns: list[Column] = []
    for raw_column in table_schema.columns:
        name = raw_column.name
        if not isinstance(name, str) or not name:
            raise ValueError("Each CSVW column must define a non-empty name")

        title = raw_column.titles
        if isinstance(title, list) and title:
            title_value = str(title[0])
        elif isinstance(title, str) and title:
            title_value = title
        else:
            title_value = name

        column = Column(
            name=name,
            title=title_value,
            datatype=_normalise_datatype(raw_column.datatype),
            required=bool(raw_column.required),
            default=(None if raw_column.default == "" else raw_column.default),
            enum_values=enums_by_name.get(name, []),
        )
        columns.append(column)

    return Schema(columns=columns, primary_key=_parse_primary_key(table_schema.primaryKey))
