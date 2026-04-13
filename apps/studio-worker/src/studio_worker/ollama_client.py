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


def _ollama_read_timeout_s() -> float:
    raw = os.environ.get("STUDIO_OLLAMA_READ_TIMEOUT_S", "").strip()
    if raw:
        try:
            return max(30.0, min(float(raw), 3600.0))
        except ValueError:
            pass
    # e2-micro + tinyllama can exceed 120s wall time under load; Cloudflare 524 hits long HTTP chains too.
    return 900.0


def chat_completion(system: str, user: str, *, model: str | None = None, timeout_s: float | None = None) -> str:
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
    read_s = float(timeout_s) if timeout_s is not None else _ollama_read_timeout_s()
    # Short connect; long read (LLM generation on small VMs routinely exceeds 120s).
    timeout = httpx.Timeout(read_s, connect=min(15.0, read_s))
    try:
        r = httpx.post(url, json=payload, timeout=timeout)
    except httpx.ReadTimeout as e:
        raise RuntimeError(
            f"Ollama read timed out at {ollama_base_url()} after ~{read_s:.0f}s ({e!r}). "
            "Raise STUDIO_OLLAMA_READ_TIMEOUT_S (seconds), add RAM/swap, use a smaller model, or mock mode."
        ) from e
    except httpx.ConnectTimeout as e:
        raise RuntimeError(
            f"Ollama connect timed out at {ollama_base_url()} ({e!r}). "
            "Is ollama running (systemctl status ollama) and OLLAMA_HOST=0.0.0.0:11434?"
        ) from e
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
