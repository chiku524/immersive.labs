from __future__ import annotations

from pathlib import Path

from studio_worker.zip_pack import zip_directory


def test_zip_directory_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "pack"
    src.mkdir()
    (src / "a.txt").write_text("hello", encoding="utf-8")
    sub = src / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world", encoding="utf-8")

    zpath = src / "pack.zip"
    zip_directory(src, zpath)
    assert zpath.is_file()
