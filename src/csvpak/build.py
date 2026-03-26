from __future__ import annotations

from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from .csvw import Schema, parse_schema
from .database import create_table, import_csv
from .redbean import DEFAULT_REDBEAN_URL, assemble, build_zip, fetch_redbean


def _lua_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_lua_columns(schema: Schema) -> str:
    lines = ["return {"]
    for column in schema.columns:
        enum_values = "{" + ", ".join(f'\"{_lua_escape(item)}\"' for item in column.enum_values) + "}"
        default_value = "nil"
        if column.default is not None:
            if isinstance(column.default, bool):
                default_value = "true" if column.default else "false"
            elif isinstance(column.default, (int, float)):
                default_value = str(column.default)
            else:
                default_value = f'\"{_lua_escape(str(column.default))}\"'

        lines.extend(
            [
                "  {",
                f'    name = \"{_lua_escape(column.name)}\",',
                f'    title = \"{_lua_escape(column.title)}\",',
                f'    datatype = \"{column.datatype}\",',
                f'    sqlite_type = \"{column.sqlite_type}\",',
                f'    html_input_type = \"{column.html_input_type}\",',
                f"    required = {'true' if column.required else 'false'},",
                f"    primary_key = {'true' if column.name in schema.primary_key else 'false'},",
                f"    default = {default_value},",
                f"    enum_values = {enum_values},",
                "  },",
            ]
        )
    lines.append("}")
    return "\n".join(lines)


def build(
    data: Path | None,
    schema: Path,
    output: Path,
    webapp_dir: Path | None = None,
    cache_dir: Path | None = None,
    redbean_url: str | None = None,
) -> Path:
    parsed_schema = parse_schema(schema)

    root_dir = Path(__file__).resolve().parents[2]
    actual_webapp_dir = webapp_dir or (root_dir / "webapp")
    actual_cache_dir = cache_dir or (Path.home() / ".cache" / "csvpak")

    if not actual_webapp_dir.exists():
        raise FileNotFoundError(f"Webapp directory not found: {actual_webapp_dir}")

    with TemporaryDirectory(prefix="csvpak-") as temp_dir:
        db_path = Path(temp_dir) / "data.sqlite"
        conn = sqlite3.connect(db_path)
        try:
            create_table(conn, parsed_schema)
            if data is not None:
                import_csv(conn, data, parsed_schema)
        finally:
            conn.close()

        lua_config = render_lua_columns(parsed_schema)
        app_title = data.name if data is not None else schema.stem
        redbean_path = fetch_redbean(actual_cache_dir, url=redbean_url or DEFAULT_REDBEAN_URL)
        archive_payload = build_zip(actual_webapp_dir, db_path, lua_config, app_title)
        assemble(redbean_path, archive_payload, output)

    return output
