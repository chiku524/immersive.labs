from __future__ import annotations

import httpx
import pytest
import respx

from studio_worker.comfy_client import run_txt2image_workflow


@respx.mock
def test_run_txt2image_workflow_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "http://comfy.test"
    monkeypatch.setenv("STUDIO_COMFY_URL", base)

    respx.post(f"{base}/prompt").mock(
        return_value=httpx.Response(200, json={"prompt_id": "pid-1"})
    )
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
