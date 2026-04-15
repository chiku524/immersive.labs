from __future__ import annotations

import httpx
import pytest
import respx

from studio_worker.comfy_client import comfy_reachability, run_txt2image_workflow


@respx.mock
def test_run_txt2image_workflow_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "http://comfy.test"
    monkeypatch.setenv("STUDIO_COMFY_URL", base)

    respx.post(f"{base}/prompt").mock(
        return_value=httpx.Response(200, json={"prompt_id": "pid-1"})
    )
    # Targeted /history/{id} not implemented → 404 → fallback to full /history (legacy).
    respx.get(f"{base}/history/pid-1").mock(return_value=httpx.Response(404, text="not found"))
    hist_empty = httpx.Response(200, json={})
    hist_done = httpx.Response(
        200,
        json={
            "pid-1": {
                "outputs": {
                    "7": {
                        "images": [
                            {
                                "filename": "out.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                }
            }
        },
    )
    respx.get(f"{base}/history").mock(side_effect=[hist_empty, hist_done])
    respx.get(f"{base}/view").mock(
        return_value=httpx.Response(200, content=b"\x89PNG\r\n\x1a\n\x00\x00")
    )

    workflow = {"7": {"class_type": "SaveImage", "inputs": {}}}
    png = run_txt2image_workflow(workflow, base_url=base)
    assert png.startswith(b"\x89PNG")


@respx.mock
def test_run_txt2image_workflow_targeted_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``GET /history/{prompt_id}`` returns outputs, skip polling the full history map."""
    base = "http://comfy.targeted"
    monkeypatch.setenv("STUDIO_COMFY_URL", base)

    respx.post(f"{base}/prompt").mock(
        return_value=httpx.Response(200, json={"prompt_id": "pid-fast"})
    )
    respx.get(f"{base}/history/pid-fast").mock(
        return_value=httpx.Response(
            200,
            json={
                "outputs": {
                    "7": {
                        "images": [
                            {
                                "filename": "fast.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                }
            },
        )
    )
    respx.get(f"{base}/view").mock(
        return_value=httpx.Response(200, content=b"\x89PNG\r\n\x1a\n\x00\x00")
    )

    workflow = {"7": {"class_type": "SaveImage", "inputs": {}}}
    png = run_txt2image_workflow(workflow, base_url=base)
    assert png.startswith(b"\x89PNG")


@respx.mock
def test_comfy_reachability_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "http://comfy.probe"
    monkeypatch.setenv("STUDIO_COMFY_URL", base)
    respx.get(f"{base}/system_stats").mock(return_value=httpx.Response(200, json={"system": {}}))
    out = comfy_reachability()
    assert out["reachable"] is True
    assert out["url"] == base.rstrip("/")


def test_comfy_reachability_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise httpx.ConnectError("refused", request=None)

    monkeypatch.setattr("studio_worker.comfy_client.httpx.get", boom)
    out = comfy_reachability(base_url="http://127.0.0.1:59999")
    assert out["reachable"] is False
    assert "refused" in (out.get("detail") or "")


@respx.mock
def test_comfy_reachability_html_error_page(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "http://comfy.html"
    monkeypatch.setenv("STUDIO_COMFY_URL", base)
    respx.get(f"{base}/system_stats").mock(
        return_value=httpx.Response(
            502,
            text="<!DOCTYPE html><html><title>Bad Gateway</title></html>",
            headers={"content-type": "text/html; charset=UTF-8"},
        )
    )
    out = comfy_reachability()
    assert out["reachable"] is False
    assert "HTML" in (out.get("detail") or "")
    assert "<!DOCTYPE" not in (out.get("detail") or "")


@respx.mock
def test_comfy_reachability_cloudflare_530(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "http://comfy.530"
    monkeypatch.setenv("STUDIO_COMFY_URL", base)
    respx.get(f"{base}/system_stats").mock(
        return_value=httpx.Response(
            530,
            text="error code: 530",
            headers={"content-type": "text/plain; charset=UTF-8", "server": "cloudflare"},
        )
    )
    out = comfy_reachability()
    assert out["reachable"] is False
    assert "530" in (out.get("detail") or "")
    assert "cloudflared" in (out.get("detail") or "").lower()


@respx.mock
def test_comfy_reachability_200_html_challenge(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "http://comfy.challenge"
    monkeypatch.setenv("STUDIO_COMFY_URL", base)
    respx.get(f"{base}/system_stats").mock(
        return_value=httpx.Response(
            200,
            text="<!DOCTYPE html><html></html>",
            headers={"content-type": "text/html"},
        )
    )
    out = comfy_reachability()
    assert out["reachable"] is False
    assert "HTML" in (out.get("detail") or "")
