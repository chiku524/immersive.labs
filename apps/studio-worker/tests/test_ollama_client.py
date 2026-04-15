from __future__ import annotations

from studio_worker.ollama_client import (
    OLLAMA_READ_TIMEOUT_MAX_S,
    _ollama_followup_read_s,
    ollama_num_predict,
    ollama_read_timeout_s,
    ollama_use_stream,
)


def test_ollama_read_timeout_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_READ_TIMEOUT_S", raising=False)
    assert ollama_read_timeout_s() == 3000.0


def test_ollama_read_timeout_clamped_from_env(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_READ_TIMEOUT_S", "900")
    assert ollama_read_timeout_s() == 900.0


def test_ollama_read_timeout_env_capped_at_max(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_READ_TIMEOUT_S", "999999")
    assert ollama_read_timeout_s() == OLLAMA_READ_TIMEOUT_MAX_S


def test_followup_read_cap() -> None:
    assert _ollama_followup_read_s(900) == 1350.0
    assert _ollama_followup_read_s(3000) == 4500.0
    assert _ollama_followup_read_s(5000) == OLLAMA_READ_TIMEOUT_MAX_S


def test_ollama_use_stream_default_on(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_STREAM", raising=False)
    assert ollama_use_stream() is True


def test_ollama_use_stream_opt_out(monkeypatch) -> None:
    for v in ("0", "false", "no", "off", "FALSE"):
        monkeypatch.setenv("STUDIO_OLLAMA_STREAM", v)
        assert ollama_use_stream() is False, v


def test_ollama_num_predict_default(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_NUM_PREDICT", raising=False)
    assert ollama_num_predict() == 4096


def test_ollama_num_predict_clamped(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_NUM_PREDICT", "200")
    assert ollama_num_predict() == 512
    monkeypatch.setenv("STUDIO_OLLAMA_NUM_PREDICT", "999999")
    assert ollama_num_predict() == 16384
