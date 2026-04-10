from __future__ import annotations

import os
from pathlib import Path

# Tests assume the monorepo layout: apps/studio-worker/tests -> repo root is parents[3]
_REPO = Path(__file__).resolve().parents[3]
os.environ.setdefault("STUDIO_REPO_ROOT", str(_REPO))
