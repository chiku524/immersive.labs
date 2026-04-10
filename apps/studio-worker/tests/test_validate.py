from __future__ import annotations

from studio_worker.mock_spec import build_mock_spec
from studio_worker.validate import validate_asset_spec


def test_mock_spec_validates_toon() -> None:
    spec = build_mock_spec(
        user_prompt="test crate",
        category="prop",
        style_preset="toon_bold",
    )
    validate_asset_spec(spec)


def test_mock_spec_validates_anime() -> None:
    spec = build_mock_spec(
        user_prompt="energy sword",
        category="prop",
        style_preset="anime_stylized",
    )
    validate_asset_spec(spec)
