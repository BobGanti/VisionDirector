from __future__ import annotations

from pathlib import Path

from flask import Flask

from smx_visiondirector import init_visiondirector
from smx_visiondirector.storage import build_sqlite_storage


class FakeGoogleVideoFile:
    def __init__(self):
        self.downloaded = False

    def save(self, path):
        if not self.downloaded:
            raise RuntimeError("file was not downloaded before save")
        Path(path).write_bytes(b"FAKE_GOOGLE_VIDEO_BYTES")


class FakeGeneratedVideo:
    def __init__(self):
        self.video = FakeGoogleVideoFile()


class FakeCompletedOperation:
    done = True

    def __init__(self):
        self.result = type(
            "Result",
            (),
            {"generated_videos": [FakeGeneratedVideo()]},
        )()


class FakePendingOperation:
    done = False


class FakeGoogleModels:
    def __init__(self, pending=False):
        self.pending = pending

    def generate_videos(self, **kwargs):
        if self.pending:
            return FakePendingOperation()
        return FakeCompletedOperation()


class FakeGoogleOperations:
    def get(self, operation):
        return FakeCompletedOperation()


class FakeGoogleFiles:
    def download(self, *, file):
        file.downloaded = True
        return None


class FakeGoogleClient:
    def __init__(self, pending=False):
        self.models = FakeGoogleModels(pending=pending)
        self.operations = FakeGoogleOperations()
        self.files = FakeGoogleFiles()


def _app(tmp_path, fake_client):
    db_path = (
        tmp_path
        / "plugins"
        / "visiondirector"
        / "data"
        / "smx_visiondirector_dev.db"
    )
    storage = build_sqlite_storage(db_path)
    storage.initialize()

    app = Flask(__name__)
    init_visiondirector(
        app,
        project_root=tmp_path,
        storage=storage,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "host-google-model",
                "client": fake_client,
            }
        },
    )
    return app


def test_google_video_route_supports_operation_result_generated_videos_and_file_download(tmp_path):
    app = _app(tmp_path, FakeGoogleClient())
    response = app.test_client().post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "cat on motorbike",
            "narrationScript": "A cat rides.",
            "aspectRatio": "16:9",
            "seconds": 4,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["url"].startswith("data:video/mp4;base64,")
    assert payload["jobId"]

    job_response = app.test_client().get(
        f"/visiondirector/api/render-jobs/{payload['jobId']}"
    )
    assert job_response.status_code == 200
    assert job_response.get_json()["job"]["status"] == "success"


def test_google_video_route_supports_operations_get_positional_polling(tmp_path):
    app = _app(tmp_path, FakeGoogleClient(pending=True))
    response = app.test_client().post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "cat on motorbike",
            "narrationScript": "A cat rides.",
            "aspectRatio": "16:9",
            "seconds": 4,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["url"].startswith("data:video/mp4;base64,")
