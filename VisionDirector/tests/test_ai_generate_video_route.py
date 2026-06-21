from __future__ import annotations

import base64

from flask import Flask

from smx_visiondirector import setup_visiondirector


class FakeGoogleModels:
    def __init__(self):
        self.calls = []

    def generate_videos(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "done": True,
            "response": {
                "generatedVideos": [
                    {
                        "video": {
                            "uri": "data:video/mp4;base64,GOOGLE_VIDEO_B64",
                            "name": "google-video-1",
                        }
                    }
                ]
            },
        }


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


class FakeOpenAIVideos:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "openai-video-1", "status": "completed"}

    def content(self, video_id):
        assert video_id == "openai-video-1"
        return b"OPENAI_VIDEO_BYTES"


class FakeOpenAIClient:
    def __init__(self):
        self.videos = FakeOpenAIVideos()


def test_generate_video_route_uses_host_google_profile_and_video_model(tmp_path):
    google = FakeGoogleClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "host-google-fallback",
                "api_key": "SECRET_GOOGLE",
                "client": google,
            }
        },
    )

    client = app.test_client()
    override = client.post(
        "/visiondirector/api/model-overrides/google",
        json={"overrides": {"VIDEO_GEN": "current-google-video-model"}},
    )
    assert override.status_code == 200

    response = client.post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "A cinematic tower",
            "narrationScript": "Welcome home.",
            "aspectRatio": "16:9",
            "seconds": "8",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["supplier"] == "google"
    assert payload["model"] == "current-google-video-model"
    assert payload["url"] == "data:video/mp4;base64,GOOGLE_VIDEO_B64"
    assert google.models.calls[-1]["model"] == "current-google-video-model"
    assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


def test_generate_video_route_uses_host_openai_profile_and_returns_data_url(tmp_path):
    openai = FakeOpenAIClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "assistant": {
                "provider": "openai",
                "model": "host-openai-fallback",
                "api_key": "SECRET_OPENAI",
                "client": openai,
            }
        },
    )

    client = app.test_client()
    override = client.post(
        "/visiondirector/api/model-overrides/openai",
        json={"overrides": {"VIDEO_GEN": "current-openai-video-model"}},
    )
    assert override.status_code == 200

    response = client.post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "openai",
            "visualPrompt": "A cinematic tower",
            "narrationScript": "Welcome home.",
            "aspectRatio": "9:16",
            "seconds": "8",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()

    expected_b64 = base64.b64encode(b"OPENAI_VIDEO_BYTES").decode("ascii")
    assert payload["supplier"] == "openai"
    assert payload["model"] == "current-openai-video-model"
    assert payload["url"] == f"data:video/mp4;base64,{expected_b64}"
    assert openai.videos.calls[-1]["model"] == "current-openai-video-model"
    assert "SECRET_OPENAI" not in response.get_data(as_text=True)


def test_runtime_js_patches_video_generation_to_backend(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "__smxVisionDirectorGenerateVideo" in body
    assert "/visiondirector/api/ai/generate-video" in body
    assert "googleProvider.generateVideo =" in body
    assert "openaiProvider.generateVideo =" in body
