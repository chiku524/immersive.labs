from __future__ import annotations

import zipfile
from pathlib import Path


def zip_directory(src_dir: Path, zip_path: Path) -> None:
    src_dir = src_dir.resolve()
    zip_path = zip_path.resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.is_file():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in src_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.resolve() == zip_path:
                continue
            if path.name == "pack.zip" and path.parent.resolve() == src_dir:
                continue
            arc = path.relative_to(src_dir)
            zf.write(path, arc.as_posix())
