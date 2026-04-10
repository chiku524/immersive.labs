from __future__ import annotations

import immersive_studio
from immersive_studio import (
    comfy_base_url,
    comfy_reachability,
    generate_asset_spec_with_metadata,
    run_studio_job,
    validate_asset_spec_file,
)


def test_sdk_version_is_non_empty() -> None:
    assert isinstance(immersive_studio.__version__, str)
    assert len(immersive_studio.__version__) > 0


def test_sdk_exports_callable() -> None:
    assert callable(run_studio_job)
    assert callable(validate_asset_spec_file)
    assert callable(generate_asset_spec_with_metadata)
    assert callable(comfy_base_url)
    assert callable(comfy_reachability)


def test_comfy_base_url_default() -> None:
    url = comfy_base_url()
    assert url.startswith("http")
