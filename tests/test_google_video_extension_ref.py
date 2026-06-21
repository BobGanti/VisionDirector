from __future__ import annotations

from pathlib import Path

from flask import Flask

from smx_visiondirector import setup_visiondirector


class FakeGoogleVideoFile:
    mime_type = "video/mp4"

    def __init__(self, label="original"):
        self.label = label
        self.name = f"fake-video-{label}"

    def save(self, path):
        Path(path).write_bytes(f"FAKE_VIDEO_BYTES_{self.label}".encode("utf-8"))


class FakeGeneratedVideo:
    def __init__(self, video):
        self.video = video


class FakeCompletedOperation:
    done = True

    def __init__(self, video):
        self.response = type("Response", (), {"generated_videos": [FakeGeneratedVideo(video)]})()


class FakeGoogleModels:
    def __init__(self):
        self.calls = []
        self.generated_count = 0

    def generate_videos(self, **kwargs):
        self.calls.append(kwargs)
        self.generated_count += 1
        return FakeCompletedOperation(FakeGoogleVideoFile(label=str(self.generated_count)))


class FakeGoogleFiles:
    def download(self, *, file):
        return None


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()
        self.files = FakeGoogleFiles()


def _app(tmp_path, fake_client):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "veo-3.1-generate-preview",
                "client": fake_client,
            }
        },
    )
    return app


def test_google_video_result_returns_opaque_extension_handle_not_serialized_video(tmp_path):
    fake_client = FakeGoogleClient()
    app = _app(tmp_path, fake_client)

    response = app.test_client().post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "cat playing football",
            "narrationScript": "A cat plays football.",
            "aspectRatio": "16:9",
            "seconds": 8,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    ref = payload["videoRef"]

    assert ref["provider"] == "google"
    assert ref["extensionHandle"].startswith("google-video-")
    assert ref["source"] == "veo_generated_video_object"
    assert ref["mimeType"] == "video/mp4"
    assert "videoBytes" not in ref
    assert "uri" not in ref


def test_google_video_extension_resolves_handle_to_original_provider_object(tmp_path):
    fake_client = FakeGoogleClient()
    app = _app(tmp_path, fake_client)

    first = app.test_client().post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "cat playing football",
            "narrationScript": "A cat plays football.",
            "aspectRatio": "16:9",
            "seconds": 8,
        },
    )

    assert first.status_code == 200
    first_ref = first.get_json()["videoRef"]
    original_provider_video_object = fake_client.models.calls[0]

    second = app.test_client().post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "The cat stopped, looked into the camera and laughed",
            "narrationScript": "",
            "aspectRatio": "16:9",
            "seconds": 8,
            "videoToExtend": first_ref,
        },
    )

    assert second.status_code == 200
    extension_call = fake_client.models.calls[-1]

    assert extension_call["video"].name == "fake-video-1"
    assert extension_call["config"] == {
        "numberOfVideos": 1,
        "resolution": "720p",
    }
    assert "aspectRatio" not in extension_call["config"]
    assert "[DIRECTOR_EXTENSION_REQUEST]" in extension_call["prompt"]


def test_google_video_extension_rejects_serialized_video_bytes_refs(tmp_path):
    fake_client = FakeGoogleClient()
    app = _app(tmp_path, fake_client)

    response = app.test_client().post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "continue the clip",
            "narrationScript": "",
            "aspectRatio": "16:9",
            "seconds": 8,
            "videoToExtend": {
                "videoBytes": "RkFLRV9WSURFTw==",
                "mimeType": "video/mp4",
            },
        },
    )

    assert response.status_code == 502
    assert "GOOGLE_EXTENSION_REQUIRES_VEO_VIDEO_OBJECT" in response.get_json()["error"]
