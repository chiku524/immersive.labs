from __future__ import annotations

import os
import re
from pathlib import Path


def _default_blocklist() -> list[str]:
    raw = os.environ.get("STUDIO_PROMPT_BLOCKLIST", "")
    if raw.strip():
        return [p.strip().lower() for p in raw.split(",") if p.strip()]
    path = os.environ.get("STUDIO_PROMPT_BLOCKLIST_FILE")
    if path:
        p = Path(path)
        if p.is_file():
            return [line.strip().lower() for line in p.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    return [
        "<script",
        "javascript:",
        "data:text/html",
    ]


def assert_prompt_allowed(user_prompt: str) -> None:
    """
    Lightweight prompt policy for internal studio use. Extend via STUDIO_PROMPT_BLOCKLIST
    (comma-separated substrings, case-insensitive) or STUDIO_PROMPT_BLOCKLIST_FILE (one phrase per line).
    """
    if os.environ.get("STUDIO_MODERATION_DISABLED", "").lower() in ("1", "true", "yes"):
        return
    text = user_prompt.lower()
    for phrase in _default_blocklist():
        if phrase and phrase in text:
            raise ValueError("Prompt blocked by studio moderation policy.")
    if len(user_prompt) > int(os.environ.get("STUDIO_PROMPT_MAX_CHARS", "8000")):
        raise ValueError("Prompt exceeds STUDIO_PROMPT_MAX_CHARS.")


def scrub_for_logs(user_prompt: str, max_len: int = 200) -> str:
    cleaned = re.sub(r"\s+", " ", user_prompt).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"
