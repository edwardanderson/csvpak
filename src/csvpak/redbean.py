from __future__ import annotations

from io import BytesIO
from pathlib import Path
import os
import stat
import time
import warnings
import zipfile

import requests

DEFAULT_REDBEAN_URL = "https://redbean.dev/redbean-2.2.com"


def _writestr_with_mode(archive: zipfile.ZipFile, arcname: str, content: bytes, mode: int) -> None:
    info = zipfile.ZipInfo(filename=arcname)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (mode & 0xFFFF) << 16
    archive.writestr(info, content)


def fetch_redbean(cache_dir: Path, url: str = DEFAULT_REDBEAN_URL) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)

    target_name = Path(url).name or "redbean.com"
    target_path = cache_dir / target_name

    if target_path.exists() and target_path.stat().st_size > 0:
        return target_path

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    target_path.write_bytes(response.content)

    mode = target_path.stat().st_mode
    target_path.chmod(mode | stat.S_IXUSR)
    return target_path


def build_zip(webapp_dir: Path, db_path: Path, lua_config: str, app_title: str) -> bytes:
    buffer = BytesIO()
    build_id = str(int(time.time() * 1000000))  # Microsecond-precision timestamp
    
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(webapp_dir.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = file_path.relative_to(webapp_dir).as_posix()
            content = file_path.read_bytes()
            _writestr_with_mode(archive, arcname, content, 0o100644)

        _writestr_with_mode(archive, "columns.lua", lua_config.encode("utf-8"), 0o100644)
        _writestr_with_mode(archive, ".args", b"-*\n...\n", 0o100644)
        _writestr_with_mode(archive, ".build_id", build_id.encode("utf-8"), 0o100644)
        _writestr_with_mode(archive, ".app_title", app_title.encode("utf-8"), 0o100644)
        _writestr_with_mode(archive, "data.sqlite", db_path.read_bytes(), 0o100644)

    return buffer.getvalue()


def assemble(redbean_path: Path, zip_bytes: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as out_file:
        out_file.write(redbean_path.read_bytes())

    with zipfile.ZipFile(output_path, "a", compression=zipfile.ZIP_DEFLATED) as output_archive:
        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as input_archive:
            with warnings.catch_warnings():
                # redbean ships built-in assets (for example .init.lua). We
                # intentionally append our own entries with the same names so
                # our app-specific files win at runtime.
                warnings.filterwarnings("ignore", message=r"Duplicate name: '.*'", category=UserWarning)
                for info in input_archive.infolist():
                    output_archive.writestr(info, input_archive.read(info.filename))

    mode = output_path.stat().st_mode
    output_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def unzip_member(distributable: Path, member_name: str, output_path: Path) -> None:
    with zipfile.ZipFile(distributable, "r") as archive:
        member_info = None
        for info in reversed(archive.infolist()):
            if info.filename == member_name:
                member_info = info
                break

        if member_info is None:
            raise FileNotFoundError(f"Member not found in archive: {member_name}")

        with archive.open(member_info) as src, output_path.open("wb") as dst:
            dst.write(src.read())

    mode = output_path.stat().st_mode
    output_path.chmod(mode | stat.S_IRUSR | stat.S_IWUSR)


def vacuum(distributable: Path) -> tuple[int, int]:
    """Remove intermediary duplicate ``data.sqlite`` entries from *distributable*.

    StoreAsset() appends a new ZIP entry each time it is called, leaving
    behind stale intermediary copies.  This command rebuilds the archive
    keeping only the **original** entry (index 0) and the **latest** entry
    (index -1) for ``data.sqlite``, while deduplicating every other asset
    to its most-recent version.

    Returns ``(before, after)`` counts of ``data.sqlite`` entries.
    """
    with zipfile.ZipFile(distributable, "r") as zf:
        all_infos = zf.infolist()
        sqlite_indices = [i for i, info in enumerate(all_infos) if info.filename == "data.sqlite"]
        before = len(sqlite_indices)

        if before <= 2:
            return before, before

        keep_set: set[int] = {sqlite_indices[0], sqlite_indices[-1]}

        # For every other asset name, keep only the last occurrence.
        seen: set[str] = set()
        other_infos: list[zipfile.ZipInfo] = []
        for info in reversed(all_infos):
            if info.filename == "data.sqlite":
                continue
            if info.filename not in seen:
                seen.add(info.filename)
                other_infos.append(info)
        other_infos.reverse()

        first_sqlite = all_infos[sqlite_indices[0]]
        last_sqlite = all_infos[sqlite_indices[-1]]

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for info in other_infos:
                out.writestr(info, zf.read(info.filename))
            out.writestr(first_sqlite, zf.open(first_sqlite).read())
            out.writestr(last_sqlite, zf.open(last_sqlite).read())

    zip_bytes = buffer.getvalue()

    # Determine where the ZIP payload starts inside the distributable so we
    # can preserve the redbean binary prefix exactly.
    with zipfile.ZipFile(distributable, "r") as zf:
        zip_start: int = zf._start_disk  # type: ignore[attr-defined]

    redbean_bytes = distributable.read_bytes()[:zip_start]

    tmp = distributable.with_suffix(".vacuum-tmp")
    try:
        tmp.write_bytes(redbean_bytes)
        with zipfile.ZipFile(tmp, "a", compression=zipfile.ZIP_DEFLATED) as out:
            with zipfile.ZipFile(BytesIO(zip_bytes), "r") as src:
                for info in src.infolist():
                    out.writestr(info, src.read(info.filename))
        mode = distributable.stat().st_mode
        tmp.chmod(mode)
        tmp.replace(distributable)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return before, 2
