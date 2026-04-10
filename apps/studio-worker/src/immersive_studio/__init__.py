"""
Immersive Studio — Python SDK alongside the ``immersive-studio`` CLI.

Install from PyPI (recommended isolated CLI via pipx)::

    pipx install immersive-studio

Or into the active environment::

    pip install immersive-studio

Example::

    from immersive_studio import run_studio_job, __version__

    result = run_studio_job(
        user_prompt="wooden barrel",
        category="prop",
        style_preset="toon_bold",
        use_mock=True,
        generate_textures=False,
        unity_urp_hint="6000.0.x LTS (pin when smoke-tested)",
        export_mesh=False,
    )
    print(result["job_id"])
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from studio_worker.comfy_client import comfy_base_url, comfy_reachability
from studio_worker.job_runner import run_studio_job
from studio_worker.spec_generate import generate_asset_spec_with_metadata
from studio_worker.validate import validate_asset_spec_file


def _read_version() -> str:
    try:
        return version("immersive-studio")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _read_version()

__all__ = [
    "__version__",
    "comfy_base_url",
    "comfy_reachability",
    "generate_asset_spec_with_metadata",
    "run_studio_job",
    "validate_asset_spec_file",
]
