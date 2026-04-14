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
    """Base seconds for each Ollama /api/chat read (connect uses a shorter cap). Second attempt uses 1.5× capped at 3600."""
    raw = os.environ.get("STUDIO_OLLAMA_READ_TIMEOUT_S", "").strip()
    if raw:
        try:
            return max(30.0, min(float(raw), 3600.0))
        except ValueError:
            pass
    # Default: 30m base read; full-job spec on slow VMs often exceeds 15m. Override via env or use mock / smaller models.
    return 1800.0


def _ollama_followup_read_s(base: float) -> float:
    """Second httpx read attempt: 1.5× base, still capped at 3600s."""
    return min(base * 1.5, 3600.0)


def _ollama_wants_stream() -> bool:
    return os.environ.get("STUDIO_OLLAMA_STREAM", "").strip().lower() in ("1", "true", "yes")


def _chat_completion_stream_once(
    system: str, user: str, *, model: str | None, read_s: float
) -> str:
    """Single streaming /api/chat attempt; may raise ReadTimeout."""
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
    out = "".join(parts).strip()
    if not out:
        raise RuntimeError("Ollama stream returned no assistant text (check model and server logs).")
    return out


def _chat_completion_stream(system: str, user: str, *, model: str | None, read_s: float) -> str:
    """Ollama ``stream: true`` — accumulates assistant deltas (NDJSON lines). Retries once with a longer read."""
    read0 = read_s
    read1 = _ollama_followup_read_s(read_s)
    last: httpx.ReadTimeout | None = None
    for attempt, attempt_read in enumerate((read0, read1)):
        try:
            return _chat_completion_stream_once(system, user, model=model, read_s=attempt_read)
        except httpx.ReadTimeout as e:
            last = e
            if attempt == 0:
                time.sleep(2.0)
                continue
        except httpx.ConnectTimeout as e:
            raise RuntimeError(
                f"Ollama connect timed out at {ollama_base_url()} ({e!r}). "
                "Is ollama running (systemctl status ollama) and OLLAMA_HOST=0.0.0.0:11434?"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Could not reach Ollama at {ollama_base_url()}: {e}") from e
    assert last is not None
    raise RuntimeError(
        f"Ollama stream read timed out at {ollama_base_url()} after 2 attempts "
        f"(~{read0:.0f}s then ~{read1:.0f}s per attempt; {last!r}). "
        f"Raise STUDIO_OLLAMA_READ_TIMEOUT_S (base is {read0:.0f}s from env or default), "
        "unset STUDIO_OLLAMA_STREAM if unstable, or use mock mode."
    ) from last


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
    read0 = read_s
    read1 = _ollama_followup_read_s(read_s)
    r: httpx.Response | None = None
    for attempt, attempt_read in enumerate((read0, read1)):
        timeout = httpx.Timeout(attempt_read, connect=min(15.0, attempt_read))
        try:
            r = httpx.post(url, json=payload, timeout=timeout)
            break
        except httpx.ReadTimeout as e:
            if attempt == 0:
                time.sleep(2.0)
                continue
            raise RuntimeError(
                f"Ollama read timed out at {ollama_base_url()} after 2 attempts "
                f"(~{read0:.0f}s then ~{read1:.0f}s per read; {e!r}). "
                f"Raise STUDIO_OLLAMA_READ_TIMEOUT_S (base seconds is {read0:.0f} from env or default; max 3600), "
                "add RAM/swap, use a smaller model (STUDIO_OLLAMA_MODEL), or mock mode."
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
