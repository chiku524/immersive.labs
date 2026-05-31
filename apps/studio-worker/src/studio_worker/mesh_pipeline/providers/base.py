from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class MeshProvider(Protocol):
    """Export a mesh GLB into a Studio pack folder."""

    pipeline_id: str

    def export_for_pack(
        self,
        pack_root: Path,
        spec: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        """Return (logs, errors). Errors are non-fatal for the overall job."""
