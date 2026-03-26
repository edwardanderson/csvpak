from __future__ import annotations

from pathlib import Path
import zipfile

from csvpak.build import build
from csvpak.export import export


def test_build_and_export_round_trip(tmp_path: Path) -> None:
    data_path = tmp_path / "people.csv"
    data_path.write_text("name,age\nAlice,31\nBob,28\n", encoding="utf-8")

    schema_path = tmp_path / "people.json"
    schema_path.write_text(
        """
{
  "@context": "http://www.w3.org/ns/csvw",
  "tables": [
    {
      "url": "people.csv",
      "tableSchema": {
        "columns": [
          {"name": "name", "datatype": "string", "required": true},
          {"name": "age", "datatype": "integer"}
        ]
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "redbean.com").write_bytes(b"REDBEAN-STUB")

    output_distributable = tmp_path / "people.redbean.com"
    build(
        data=data_path,
        schema=schema_path,
        output=output_distributable,
        cache_dir=cache_dir,
    )

    assert output_distributable.exists()
    assert output_distributable.stat().st_size > len(b"REDBEAN-STUB")

    with zipfile.ZipFile(output_distributable, "r") as archive:
        assert "data.sqlite" in archive.namelist()
        assert "data.csv" not in archive.namelist()
        assert archive.read(".app_title").decode("utf-8") == "people.csv"

    exported_csv = tmp_path / "exported.csv"
    row_count = export(output_distributable, exported_csv)

    assert row_count == 2
    assert exported_csv.read_text(encoding="utf-8").splitlines() == [
        "name,age",
        "Alice,31",
        "Bob,28",
    ]


def test_build_with_schema_only_initialises_empty_database(tmp_path: Path) -> None:
    schema_path = tmp_path / "people.json"
    schema_path.write_text(
        """
{
  "@context": "http://www.w3.org/ns/csvw",
  "tables": [
    {
      "url": "people.csv",
      "tableSchema": {
        "columns": [
          {"name": "name", "datatype": "string", "required": true},
          {"name": "age", "datatype": "integer"}
        ]
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "redbean.com").write_bytes(b"REDBEAN-STUB")

    output_distributable = tmp_path / "people-empty.redbean.com"
    build(
        data=None,
        schema=schema_path,
        output=output_distributable,
        cache_dir=cache_dir,
    )

    assert output_distributable.exists()

    exported_csv = tmp_path / "exported-empty.csv"
    row_count = export(output_distributable, exported_csv)

    assert row_count == 0
    assert exported_csv.read_text(encoding="utf-8").splitlines() == ["name,age"]
