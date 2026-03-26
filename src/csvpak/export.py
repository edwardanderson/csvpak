from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from .database import export_csv
from .redbean import unzip_member


def extract_db(distributable: Path, output_path: Path) -> Path:
    """Extract the latest ``data.sqlite`` from *distributable*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    unzip_member(distributable, "data.sqlite", output_path)
    return output_path


def export(distributable: Path, output: Path) -> int:
    """Export the current data from *distributable* to a CSV at *output*."""
    with TemporaryDirectory(prefix="csvpak-export-") as temp_dir:
        db_path = Path(temp_dir) / "data.sqlite"
        extract_db(distributable, db_path)
        return export_csv(db_path, output)
