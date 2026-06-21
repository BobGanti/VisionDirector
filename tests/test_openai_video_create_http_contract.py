from __future__ import annotations

import json
from types import SimpleNamespace

from smx_visiondirector import ai_runtime
from smx_visiondirector.ai_runtime import (
    _smx_openai_create_video_via_json_endpoint,
    _smx_openai_input_reference_json,
)


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def test_openai_input_reference_json_accepts_data_url():
    ref = _smx_openai_input_reference_json("data:image/png;base64,AAAA")

    assert ref == {"image_url": "data:image/png;base64,AAAA"}


def test_openai_input_reference_json_wraps_raw_base64_as_png_data_url():
    ref = _smx_openai_input_reference_json("AAAA")

    assert ref == {"image_url": "data:image/png;base64,AAAA"}


def test_openai_raw_json_create_posts_input_reference(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(b'{"id":"video_123","status":"queued"}')

    monkeypatch.setattr(ai_runtime.urllib.request, "urlopen", fake_urlopen)

    client = SimpleNamespace(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
    )
    profile = SimpleNamespace(api_key="sk-profile")

    result = _smx_openai_create_video_via_json_endpoint(
        client,
        profile=profile,
        model="sora-2",
        prompt="animate this starting frame",
        seconds="8",
        size="1280x720",
        start_image_base64="data:image/png;base64,AAAA",
    )

    assert result["id"] == "video_123"
    assert captured["url"] == "https://api.openai.com/v1/videos"
    assert captured["body"] == {
        "model": "sora-2",
        "prompt": "animate this starting frame",
        "seconds": "8",
        "size": "1280x720",
        "input_reference": {"image_url": "data:image/png;base64,AAAA"},
    }
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["Content-type"] == "application/json"
