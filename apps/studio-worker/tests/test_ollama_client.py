from __future__ import annotations

from studio_worker.ollama_client import (
    OLLAMA_READ_TIMEOUT_MAX_S,
    _ollama_followup_read_s,
    _ollama_preflight,
    effective_use_mock,
    ollama_connect_timeout_s,
    ollama_json_format_enabled,
    ollama_num_predict,
    ollama_preflight_enabled,
    ollama_read_timeout_s,
    ollama_use_stream,
    ollama_verify_model_enabled,
)


def test_ollama_read_timeout_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_READ_TIMEOUT_S", raising=False)
    assert ollama_read_timeout_s() == 600.0


def test_ollama_read_timeout_clamped_from_env(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_READ_TIMEOUT_S", "900")
    assert ollama_read_timeout_s() == 900.0


def test_ollama_read_timeout_env_capped_at_max(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_READ_TIMEOUT_S", "999999")
    assert ollama_read_timeout_s() == OLLAMA_READ_TIMEOUT_MAX_S


def test_followup_read_cap() -> None:
    assert _ollama_followup_read_s(900) == 1350.0
    assert _ollama_followup_read_s(3000) == 3600.0
    assert _ollama_followup_read_s(12000) == OLLAMA_READ_TIMEOUT_MAX_S


def test_ollama_read_timeout_min_clamp(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_READ_TIMEOUT_S", "9")
    assert ollama_read_timeout_s() == 15.0


def test_ollama_connect_timeout_default(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_CONNECT_TIMEOUT_S", raising=False)
    assert ollama_connect_timeout_s() == 8.0


def test_ollama_connect_timeout_clamped(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_CONNECT_TIMEOUT_S", "999")
    assert ollama_connect_timeout_s() == 60.0


def test_effective_use_mock_respects_ollama_disabled(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_DISABLED", raising=False)
    assert effective_use_mock(False) is False
    monkeypatch.setenv("STUDIO_OLLAMA_DISABLED", "1")
    assert effective_use_mock(False) is True


def test_preflight_opt_out(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_PREFLIGHT", "0")
    assert ollama_preflight_enabled() is False


def test_verify_model_opt_out(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_VERIFY_MODEL", "0")
    assert ollama_verify_model_enabled() is False


def test_preflight_model_mismatch(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_PREFLIGHT", raising=False)
    monkeypatch.delenv("STUDIO_OLLAMA_VERIFY_MODEL", raising=False)
    monkeypatch.setenv("STUDIO_OLLAMA_MODEL", "not-installed-abc")

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"models": [{"name": "llama3.2:latest"}]}

    monkeypatch.setattr("studio_worker.ollama_client.httpx.get", lambda url, timeout=None: FakeResp())

    try:
        _ollama_preflight(model=None)
    except RuntimeError as e:
        assert "not available" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_preflight_model_match(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_PREFLIGHT", raising=False)
    monkeypatch.delenv("STUDIO_OLLAMA_VERIFY_MODEL", raising=False)
    monkeypatch.setenv("STUDIO_OLLAMA_MODEL", "tinyllama")

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"models": [{"name": "tinyllama:latest"}]}

    monkeypatch.setattr("studio_worker.ollama_client.httpx.get", lambda url, timeout=None: FakeResp())
    _ollama_preflight(model=None)


def test_preflight_skips_model_check_when_verify_off(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_PREFLIGHT", raising=False)
    monkeypatch.setenv("STUDIO_OLLAMA_VERIFY_MODEL", "0")
    monkeypatch.setenv("STUDIO_OLLAMA_MODEL", "not-installed-abc")

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"models": [{"name": "llama3.2:latest"}]}

    monkeypatch.setattr("studio_worker.ollama_client.httpx.get", lambda url, timeout=None: FakeResp())
    _ollama_preflight(model=None)


def test_ollama_use_stream_default_on(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_STREAM", raising=False)
    assert ollama_use_stream() is True


def test_ollama_use_stream_opt_out(monkeypatch) -> None:
    for v in ("0", "false", "no", "off", "FALSE"):
        monkeypatch.setenv("STUDIO_OLLAMA_STREAM", v)
        assert ollama_use_stream() is False, v


def test_ollama_num_predict_default(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_NUM_PREDICT", raising=False)
    assert ollama_num_predict() == 2048


def test_ollama_json_format_default_on(monkeypatch) -> None:
    monkeypatch.delenv("STUDIO_OLLAMA_JSON_FORMAT", raising=False)
    assert ollama_json_format_enabled() is True


def test_ollama_json_format_opt_out(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_JSON_FORMAT", "0")
    assert ollama_json_format_enabled() is False


def test_ollama_num_predict_clamped(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_OLLAMA_NUM_PREDICT", "200")
    assert ollama_num_predict() == 512
    monkeypatch.setenv("STUDIO_OLLAMA_NUM_PREDICT", "999999")
    assert ollama_num_predict() == 16384
