from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

OLLAMA_URL_DEFAULT = "http://127.0.0.1:11434"
MODEL_DEFAULT = "llama3.2"


def ollama_base_url() -> str:
    return os.environ.get("STUDIO_OLLAMA_URL", OLLAMA_URL_DEFAULT).rstrip("/")


def ollama_model() -> str:
    return os.environ.get("STUDIO_OLLAMA_MODEL", MODEL_DEFAULT)


def ollama_read_timeout_s() -> float:
    """Max seconds to wait for a single Ollama /api/chat response (connect uses a shorter cap)."""
    raw = os.environ.get("STUDIO_OLLAMA_READ_TIMEOUT_S", "").strip()
    if raw:
        try:
            return max(30.0, min(float(raw), 3600.0))
        except ValueError:
            pass
    # Default raised from 900s: small VMs + larger models often need 15–25+ minutes without timing out.
    return 1200.0


def _ollama_wants_stream() -> bool:
    return os.environ.get("STUDIO_OLLAMA_STREAM", "").strip().lower() in ("1", "true", "yes")


def _chat_completion_stream(system: str, user: str, *, model: str | None, read_s: float) -> str:
    """Ollama ``stream: true`` — accumulates assistant deltas (NDJSON lines)."""
    m = model or ollama_model()
    url = f"{ollama_base_url()}/api/chat"
    payload: dict[str, Any] = {
        "model": m,
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.35},
    }
    timeout = httpx.Timeout(read_s, connect=min(15.0, read_s))
    parts: list[str] = []
    with httpx.Client() as client:
        try:
            with client.stream("POST", url, json=payload, timeout=timeout) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        chunk: dict[str, Any] = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("done"):
                        break
                    msg = chunk.get("message") or {}
                    c = msg.get("content")
                    if isinstance(c, str) and c:
                        parts.append(c)
        except httpx.ReadTimeout as e:
            raise RuntimeError(
                f"Ollama stream read timed out at {ollama_base_url()} after ~{read_s:.0f}s ({e!r}). "
                "Unset STUDIO_OLLAMA_STREAM, raise STUDIO_OLLAMA_READ_TIMEOUT_S, or use mock mode."
            ) from e
        except httpx.ConnectTimeout as e:
            raise RuntimeError(
                f"Ollama connect timed out at {ollama_base_url()} ({e!r}). "
                "Is ollama running (systemctl status ollama) and OLLAMA_HOST=0.0.0.0:11434?"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Could not reach Ollama at {ollama_base_url()}: {e}") from e
    out = "".join(parts).strip()
    if not out:
        raise RuntimeError("Ollama stream returned no assistant text (check model and server logs).")
    return out


def chat_completion(system: str, user: str, *, model: str | None = None, timeout_s: float | None = None) -> str:
    read_s = float(timeout_s) if timeout_s is not None else ollama_read_timeout_s()
    if _ollama_wants_stream():
        return _chat_completion_stream(system, user, model=model, read_s=read_s)
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
    # Short connect; long read (LLM generation on small VMs routinely exceeds 120s).
    timeout = httpx.Timeout(read_s, connect=min(15.0, read_s))
    r: httpx.Response | None = None
    for attempt in range(2):
        try:
            r = httpx.post(url, json=payload, timeout=timeout)
            break
        except httpx.ReadTimeout as e:
            if attempt == 0:
                time.sleep(2.0)
                continue
            raise RuntimeError(
                f"Ollama read timed out at {ollama_base_url()} after ~{read_s:.0f}s (2 attempts, {e!r}). "
                "Raise STUDIO_OLLAMA_READ_TIMEOUT_S (seconds), add RAM/swap, use a smaller model (STUDIO_OLLAMA_MODEL), or mock mode."
            ) from e
        except httpx.ConnectTimeout as e:
            raise RuntimeError(
                f"Ollama connect timed out at {ollama_base_url()} ({e!r}). "
                "Is ollama running (systemctl status ollama) and OLLAMA_HOST=0.0.0.0:11434?"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Could not reach Ollama at {ollama_base_url()}: {e}") from e
    assert r is not None
    if r.status_code >= 400:
        raise RuntimeError(f"Ollama error {r.status_code}: {r.text[:500]}")
    data: dict[str, Any] = r.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"Unexpected Ollama response: {json.dumps(data)[:800]}")
    return content
