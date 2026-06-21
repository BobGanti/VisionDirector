from __future__ import annotations

import json
from types import SimpleNamespace

from smx_visiondirector import ai_runtime
from smx_visiondirector.ai_runtime import _smx_openai_extend_video_via_json_endpoint


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def test_openai_raw_json_extension_posts_video_id_object(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(b'{"id":"video_ext_123","status":"queued"}')

    monkeypatch.setattr(ai_runtime.urllib.request, "urlopen", fake_urlopen)

    client = SimpleNamespace(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
    )
    profile = SimpleNamespace(api_key="sk-profile")

    result = _smx_openai_extend_video_via_json_endpoint(
        client,
        profile=profile,
        prompt="continue the clip",
        seconds="8",
        video_to_extend={"providerVideoId": "video_123"},
    )

    assert result["id"] == "video_ext_123"
    assert captured["url"] == "https://api.openai.com/v1/videos/extensions"
    assert captured["body"] == {
        "prompt": "continue the clip",
        "seconds": "8",
        "video": {"id": "video_123"},
    }
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["Content-type"] == "application/json"
