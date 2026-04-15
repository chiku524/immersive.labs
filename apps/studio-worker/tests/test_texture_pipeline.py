from __future__ import annotations

import pytest

from studio_worker.texture_pipeline import texture_output_dimensions


def test_texture_output_dimensions_from_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_TEXTURE_MAX_SIDE", "4096")
    spec = {
        "style_preset": "toon_bold",
        "material_slots": [
            {"id": "main", "role": "albedo", "resolution_hint": 2048},
            {"id": "main", "role": "normal", "resolution_hint": 2048},
        ],
    }
    w, h = texture_output_dimensions(spec)
    assert w == h == 1024

def test_texture_output_dimensions_realistic_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_TEXTURE_MAX_SIDE", "8192")
    monkeypatch.setenv("STUDIO_TEXTURE_MAX_SIDE_REALISTIC_HD_PBR", "2048")
    spec = {
        "style_preset": "realistic_hd_pbr",
        "material_slots": [{"id": "m", "role": "albedo", "resolution_hint": 4096}],
    }
    w, h = texture_output_dimensions(spec)
    assert w == h == 2048
