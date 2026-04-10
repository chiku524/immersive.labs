#!/usr/bin/env python3
"""
Keep the bundled JSON Schema under apps/studio-worker in sync with the canonical
copy in packages/studio-types (used by PyPI wheels and runtime validation).

Usage:
  python scripts/sync-studio-asset-schema.py           # copy canonical → bundled
  python scripts/sync-studio-asset-schema.py --check   # exit 1 if they differ (CI)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_SCHEMA_NAME = "studio-asset-spec-v0.1.schema.json"


def _paths() -> tuple[Path, Path]:
    repo = Path(__file__).resolve().parents[1]
    canonical = repo / "packages" / "studio-types" / "schema" / _SCHEMA_NAME
    bundled = repo / "apps" / "studio-worker" / "src" / "studio_worker" / "data" / _SCHEMA_NAME
    return canonical, bundled


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare files; exit 1 if they differ (does not write).",
    )
    args = parser.parse_args()
    canonical, bundled = _paths()

    if not canonical.is_file():
        print(f"error: canonical schema missing: {canonical}", file=sys.stderr)
        return 2

    if args.check:
        if not bundled.is_file():
            print(f"error: bundled schema missing: {bundled}", file=sys.stderr)
            return 1
        a, b = canonical.read_bytes(), bundled.read_bytes()
        if a != b:
            print(
                "error: bundled schema differs from canonical.\n"
                f"  canonical: {canonical}\n"
                f"  bundled:   {bundled}\n"
                "Run: python scripts/sync-studio-asset-schema.py",
                file=sys.stderr,
            )
            return 1
        print("OK: bundled schema matches canonical.")
        return 0

    bundled.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(canonical, bundled)
    print(f"Copied {canonical} -> {bundled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
