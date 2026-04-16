from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

OLLAMA_URL_DEFAULT = "http://127.0.0.1:11434"
MODEL_DEFAULT = "llama3.2"

# httpx read timeout per /api/chat attempt: Ollama returns as soon as generation finishes (no extra
# charge for unused seconds). Higher caps only hurt if the model hangs — the queue worker blocks until read timeout.
# Default 600s: enough for modest JSON specs on small VMs; raise via STUDIO_OLLAMA_READ_TIMEOUT_S if truncated.
OLLAMA_READ_TIMEOUT_DEFAULT_S = 600.0
# Cap for env STUDIO_OLLAMA_READ_TIMEOUT_S and for the 2nd read attempt (1.5× base, also capped here).
OLLAMA_READ_TIMEOUT_MAX_S = 3600.0
# JSON game specs are usually <2k tokens; lower default finishes sooner on small VMs (raise via env if truncated).
OLLAMA_NUM_PREDICT_DEFAULT = 2048
OLLAMA_NUM_PREDICT_MIN = 512
OLLAMA_NUM_PREDICT_MAX = 16384


def ollama_base_url() -> str:
    return os.environ.get("STUDIO_OLLAMA_URL", OLLAMA_URL_DEFAULT).rstrip("/")


def ollama_model() -> str:
    return os.environ.get("STUDIO_OLLAMA_MODEL", MODEL_DEFAULT)


def ollama_read_timeout_s() -> float:
    """Base seconds for each Ollama /api/chat read (connect uses a shorter cap). Second attempt uses 1.5× capped at OLLAMA_READ_TIMEOUT_MAX_S."""
    raw = os.environ.get("STUDIO_OLLAMA_READ_TIMEOUT_S", "").strip()
    if raw:
        try:
            return max(15.0, min(float(raw), OLLAMA_READ_TIMEOUT_MAX_S))
        except ValueError:
            pass
    return OLLAMA_READ_TIMEOUT_DEFAULT_S


def ollama_connect_timeout_s() -> float:
    """TCP connect timeout for Ollama HTTP calls (seconds). Fail fast when nothing listens on STUDIO_OLLAMA_URL."""
    raw = os.environ.get("STUDIO_OLLAMA_CONNECT_TIMEOUT_S", "").strip()
    if raw:
        try:
            return max(2.0, min(float(raw), 60.0))
        except ValueError:
            pass
    return 8.0


def ollama_preflight_enabled() -> bool:
    """When True (default), call GET /api/tags before /api/chat so dead servers fail in ~seconds instead of one read cycle."""
    raw = os.environ.get("STUDIO_OLLAMA_PREFLIGHT", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def ollama_verify_model_enabled() -> bool:
    """When True (default), after /api/tags succeeds ensure STUDIO_OLLAMA_MODEL is present (avoids opaque generate errors)."""
    raw = os.environ.get("STUDIO_OLLAMA_VERIFY_MODEL", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def ollama_disabled() -> bool:
    """
    When True, workers skip Ollama and use the same deterministic mock spec path as client ``mock: true``.
    Set STUDIO_OLLAMA_DISABLED=1 on hosts without a local LLM to avoid wedged queue jobs.
    """
    raw = os.environ.get("STUDIO_OLLAMA_DISABLED", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def effective_use_mock(requested_mock: bool) -> bool:
    return bool(requested_mock) or ollama_disabled()


def _ollama_followup_read_s(base: float) -> float:
    """Second httpx read attempt: 1.5× base, capped at OLLAMA_READ_TIMEOUT_MAX_S."""
    return min(base * 1.5, OLLAMA_READ_TIMEOUT_MAX_S)


def ollama_use_stream() -> bool:
    """
    Streaming /api/chat sends NDJSON chunks; httpx read timeouts apply between chunks, so slow
    but steady token generation is far less likely to hit a wall-clock read timeout than one
    blocking response (``stream: false``). Opt out with STUDIO_OLLAMA_STREAM=0|false|no|off.
    """
    raw = os.environ.get("STUDIO_OLLAMA_STREAM", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def ollama_num_predict() -> int:
    """Max tokens to generate per spec call (Ollama ``options.num_predict``)."""
    raw = os.environ.get("STUDIO_OLLAMA_NUM_PREDICT", "").strip()
    if not raw:
        return OLLAMA_NUM_PREDICT_DEFAULT
    try:
        n = int(float(raw))
    except ValueError:
        return OLLAMA_NUM_PREDICT_DEFAULT
    return max(OLLAMA_NUM_PREDICT_MIN, min(n, OLLAMA_NUM_PREDICT_MAX))


def ollama_json_format_enabled() -> bool:
    """When True, send Ollama ``format: json`` on /api/chat (tighter JSON, often shorter generations)."""
    raw = os.environ.get("STUDIO_OLLAMA_JSON_FORMAT", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def ollama_keep_alive() -> str | None:
    """Optional Ollama ``keep_alive`` (e.g. ``30m``, ``-1``). Unset = omit from request."""
    raw = os.environ.get("STUDIO_OLLAMA_KEEP_ALIVE", "").strip()
    return raw or None


def _ollama_num_ctx_optional() -> int | None:
    raw = os.environ.get("STUDIO_OLLAMA_NUM_CTX", "").strip()
    if not raw:
        return None
    try:
        n = int(float(raw))
    except ValueError:
        return None
    return max(512, min(n, 32768))


def _ollama_chat_options() -> dict[str, Any]:
    opts: dict[str, Any] = {"temperature": 0.35, "num_predict": ollama_num_predict()}
    nc = _ollama_num_ctx_optional()
    if nc is not None:
        opts["num_ctx"] = nc
    return opts


def _model_tag_matches_configured(tag_name: str, *, configured: str) -> bool:
    """``tinyllama`` matches ``tinyllama:latest``; ``llama3.2`` matches ``llama3.2:3b``."""
    cfg = configured.strip().lower()
    if not cfg:
        return False
    cfg_base = cfg.split(":", 1)[0]
    tag = tag_name.strip().lower()
    tag_base = tag.split(":", 1)[0]
    return tag == cfg or tag.startswith(cfg + ":") or tag_base == cfg_base


def _ollama_preflight(*, model: str | None) -> None:
    if not ollama_preflight_enabled():
        return
    url = f"{ollama_base_url()}/api/tags"
    c = ollama_connect_timeout_s()
    timeout = httpx.Timeout(25.0, connect=c)
    try:
        r = httpx.get(url, timeout=timeout)
    except httpx.ConnectTimeout as e:
        raise RuntimeError(
            f"Ollama preflight: connect timed out to {ollama_base_url()} ({e!r}). "
            "Is ollama running and listening (e.g. OLLAMA_HOST=0.0.0.0:11434)? "
            "Or set STUDIO_OLLAMA_DISABLED=1 to use mock specs without a local LLM."
        ) from e
    except httpx.RequestError as e:
        raise RuntimeError(
            f"Ollama preflight: could not reach {ollama_base_url()}: {e}. "
            "Set STUDIO_OLLAMA_DISABLED=1 to skip the LLM when Ollama is intentionally absent."
        ) from e
    if r.status_code >= 400:
        raise RuntimeError(
            f"Ollama preflight: {url} returned HTTP {r.status_code}: {r.text[:400]!r}"
        )
    m = model or ollama_model()
    if not ollama_verify_model_enabled():
        return
    try:
        data: dict[str, Any] = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Ollama preflight: invalid JSON from {url}: {e!r}") from e
    models = data.get("models")
    if not isinstance(models, list):
        raise RuntimeError(f"Ollama preflight: unexpected /api/tags shape (no models list): {str(data)[:400]}")
    names: list[str] = []
    for item in models:
        if isinstance(item, dict):
            n = item.get("name")
            if isinstance(n, str) and n.strip():
                names.append(n.strip())
    if not names:
        raise RuntimeError(
            "Ollama preflight: server has no models installed (`ollama list` empty). "
            f"Pull the configured model: ollama pull {m!r}"
        )
    if not any(_model_tag_matches_configured(n, configured=m) for n in names):
        raise RuntimeError(
            f"Ollama preflight: model {m!r} is not available. Installed: {names[:12]!r}. "
            f"Run: ollama pull {m.split(':', 1)[0]!r}"
        )


def _chat_payload_common(
    system: str, user: str, *, model: str | None, stream: bool, format_json: bool
) -> dict[str, Any]:
    m = model or ollama_model()
    payload: dict[str, Any] = {
        "model": m,
        "stream": stream,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": _ollama_chat_options(),
    }
    if format_json and ollama_json_format_enabled():
        payload["format"] = "json"
    ka = ollama_keep_alive()
    if ka is not None:
        payload["keep_alive"] = ka
    return payload


def _chat_completion_stream_once(
    system: str, user: str, *, model: str | None, read_s: float, format_json: bool
) -> str:
    """Single streaming /api/chat attempt; may raise ReadTimeout."""
    url = f"{ollama_base_url()}/api/chat"
    payload = _chat_payload_common(system, user, model=model, stream=True, format_json=format_json)
    cto = ollama_connect_timeout_s()
    timeout = httpx.Timeout(read_s, connect=min(cto, read_s))
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


def _chat_completion_stream(
    system: str, user: str, *, model: str | None, read_s: float, format_json: bool
) -> str:
    """Ollama ``stream: true`` — accumulates assistant deltas (NDJSON lines). Retries once with a longer read."""
    read0 = read_s
    read1 = _ollama_followup_read_s(read_s)
    last: httpx.ReadTimeout | None = None
    for attempt, attempt_read in enumerate((read0, read1)):
        try:
            return _chat_completion_stream_once(
                system, user, model=model, read_s=attempt_read, format_json=format_json
            )
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
        f"Raise STUDIO_OLLAMA_READ_TIMEOUT_S (base is {read0:.0f}s from env or default; max {OLLAMA_READ_TIMEOUT_MAX_S:.0f}), "
        "remove stale 900s caps from VM metadata, set STUDIO_OLLAMA_STREAM=0 only if NDJSON streaming misbehaves, "
        "or use mock mode."
    ) from last


def chat_completion(
    system: str,
    user: str,
    *,
    model: str | None = None,
    timeout_s: float | None = None,
    format_json: bool = True,
) -> str:
    _ollama_preflight(model=model)
    read_s = float(timeout_s) if timeout_s is not None else ollama_read_timeout_s()
    if ollama_use_stream():
        return _chat_completion_stream(system, user, model=model, read_s=read_s, format_json=format_json)
    url = f"{ollama_base_url()}/api/chat"
    payload = _chat_payload_common(system, user, model=model, stream=False, format_json=format_json)
    read0 = read_s
    read1 = _ollama_followup_read_s(read_s)
    r: httpx.Response | None = None
    for attempt, attempt_read in enumerate((read0, read1)):
        cto = ollama_connect_timeout_s()
        timeout = httpx.Timeout(attempt_read, connect=min(cto, attempt_read))
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
                f"Raise STUDIO_OLLAMA_READ_TIMEOUT_S (base seconds is {read0:.0f} from env or default; max {OLLAMA_READ_TIMEOUT_MAX_S:.0f}), "
                "clear stale 900s from GCE/Docker env if you never set a higher cap, add RAM/swap, "
                "use a smaller model (STUDIO_OLLAMA_MODEL), lower STUDIO_OLLAMA_NUM_PREDICT, or mock mode."
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
