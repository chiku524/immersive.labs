from __future__ import annotations

import json
import os
from typing import Any

import httpx

OLLAMA_URL_DEFAULT = "http://127.0.0.1:11434"
MODEL_DEFAULT = "llama3.2"


def ollama_base_url() -> str:
    return os.environ.get("STUDIO_OLLAMA_URL", OLLAMA_URL_DEFAULT).rstrip("/")


def ollama_model() -> str:
    return os.environ.get("STUDIO_OLLAMA_MODEL", MODEL_DEFAULT)


def chat_completion(system: str, user: str, *, model: str | None = None, timeout_s: float = 120.0) -> str:
    m = model or ollama_model()
    url = f"{ollama_base_url()}/api/chat"
    payload = {
        "model": m,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.35},
    }
    try:
        r = httpx.post(url, json=payload, timeout=timeout_s)
    except httpx.RequestError as e:
        raise RuntimeError(f"Could not reach Ollama at {ollama_base_url()}: {e}") from e
    if r.status_code >= 400:
        raise RuntimeError(f"Ollama error {r.status_code}: {r.text[:500]}")
    data: dict[str, Any] = r.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"Unexpected Ollama response: {json.dumps(data)[:800]}")
    return content
