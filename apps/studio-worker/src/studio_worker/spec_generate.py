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
from studio_worker.prompts import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_STYLE_PRESET,
    system_prompt,
    user_prompt_block,
)
from studio_worker.validate import apply_llm_json_coercions, validate_asset_spec


def _pin_generation_source_prompt(spec: dict[str, Any], user_prompt: str) -> None:
    """Tripo text-to-3D reads ``generation.source_prompt`` — always use the user's exact brief."""
    gen = spec.get("generation")
    if not isinstance(gen, dict):
        gen = {}
        spec["generation"] = gen
    gen["source_prompt"] = user_prompt.strip()


def generate_asset_spec(
    *,
    user_prompt: str,
    use_mock: bool = False,
) -> dict[str, Any]:
    assert_prompt_allowed(user_prompt)

    if use_mock:
        spec = build_mock_spec(
            user_prompt=user_prompt,
            category=DEFAULT_CATEGORY,
            style_preset=DEFAULT_STYLE_PRESET,
        )
        _pin_generation_source_prompt(spec, user_prompt)
        validate_asset_spec(spec)
        return spec

    system = system_prompt()
    user = user_prompt_block(user_prompt)
    raw = chat_completion(system, user)
    try:
        spec = extract_json_object(raw)
    except ValueError:
        repair_user = (
            f"{user}\n\n"
            "Your previous reply was not valid JSON. Return ONLY one compact JSON object "
            "matching the schema (no markdown fences, no comments, no trailing commas)."
        )
        raw = chat_completion(system, repair_user)
        spec = extract_json_object(raw)
    apply_llm_json_coercions(spec)
    spec["style_preset"] = DEFAULT_STYLE_PRESET
    if spec.get("category") not in CATEGORIES:
        spec["category"] = DEFAULT_CATEGORY
    _pin_generation_source_prompt(spec, user_prompt)
    validate_asset_spec(spec)
    return spec


def generate_asset_spec_with_metadata(
    *,
    user_prompt: str,
    use_mock: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    effective_mock = bool(use_mock) or ollama_disabled()
    spec = generate_asset_spec(
        user_prompt=user_prompt,
        use_mock=effective_mock,
    )
    meta: dict[str, Any] = {
        "llm_model": None if effective_mock else f"ollama:{ollama_model()}",
        "mock": effective_mock,
        "ollama_disabled": ollama_disabled(),
    }
    return spec, meta
