from __future__ import annotations

from typing import Any

from studio_worker.json_extract import extract_json_object
from studio_worker.mock_spec import build_mock_spec
from studio_worker.moderation import assert_prompt_allowed
from studio_worker.ollama_client import (
    chat_completion,
    ollama_disabled,
    ollama_model,
)
from studio_worker.prompts import CATEGORIES, STYLE_PRESETS, system_prompt_for_style, user_prompt_block
from studio_worker.validate import apply_llm_json_coercions, validate_asset_spec


def generate_asset_spec(
    *,
    user_prompt: str,
    category: str,
    style_preset: str,
    use_mock: bool = False,
) -> dict[str, Any]:
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}")
    if style_preset not in STYLE_PRESETS:
        raise ValueError(f"style_preset must be one of {STYLE_PRESETS}")

    assert_prompt_allowed(user_prompt)

    if use_mock:
        spec = build_mock_spec(
            user_prompt=user_prompt, category=category, style_preset=style_preset
        )
        validate_asset_spec(spec)
        return spec

    system = system_prompt_for_style(style_preset)
    user = user_prompt_block(user_prompt, category)
    raw = chat_completion(system, user)
    spec = extract_json_object(raw)
    # Belt-and-suspenders before mutating style/category (normalize also runs inside validate).
    apply_llm_json_coercions(spec)
    spec["style_preset"] = style_preset
    spec["category"] = category
    validate_asset_spec(spec)
    return spec


def generate_asset_spec_with_metadata(
    *,
    user_prompt: str,
    category: str,
    style_preset: str,
    use_mock: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    effective_mock = bool(use_mock) or ollama_disabled()
    spec = generate_asset_spec(
        user_prompt=user_prompt,
        category=category,
        style_preset=style_preset,
        use_mock=effective_mock,
    )
    meta: dict[str, Any] = {
        "llm_model": None if effective_mock else f"ollama:{ollama_model()}",
        "mock": effective_mock,
        "ollama_disabled": ollama_disabled(),
    }
    return spec, meta
