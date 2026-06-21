from __future__ import annotations

import sqlite3

from flask import Flask

from smx_visiondirector import init_visiondirector
from smx_visiondirector.storage import SQLiteRenderJobStore, build_sqlite_storage


class FailingGoogleModels:
    def generate_videos(self, **kwargs):
        raise RuntimeError("provider video failure")


class FailingGoogleClient:
    def __init__(self):
        self.models = FailingGoogleModels()


def test_sqlite_render_job_store_records_success_and_error(tmp_path):
    db_path = (
        tmp_path
        / "plugins"
        / "visiondirector"
        / "data"
        / "smx_visiondirector_dev.db"
    )
    storage = build_sqlite_storage(db_path)
    storage.initialize()

    store = SQLiteRenderJobStore(storage)
    store.create(
        job_id="job-1",
        supplier="google",
        prompt="cat on motorbike",
        model="veo-test",
    )
    store.mark_error(job_id="job-1", error="provider failed")

    job = store.get("job-1")
    assert job is not None
    assert job["status"] == "error"
    assert job["error"] == "provider failed"

    store.create(
        job_id="job-2",
        supplier="google",
        prompt="dog on bicycle",
        model="veo-test",
    )
    store.mark_success(
        job_id="job-2",
        video_url="data:video/mp4;base64,abc",
        video_ref={"id": "remote-video"},
    )

    success = store.get("job-2")
    assert success is not None
    assert success["status"] == "success"
    assert success["videoUrl"] is None
    assert success["videoRef"]["id"] == "remote-video"
    assert success["videoRef"]["storage"] == "not_persisted"
    assert success["videoRef"]["reason"] == "large_video_data_url"
    assert success["videoRef"]["id"] == "remote-video"


def test_generate_video_failure_records_render_job(tmp_path):
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
                "client": FailingGoogleClient(),
            }
        },
    )

    client = app.test_client()
    response = client.post(
        "/visiondirector/api/ai/generate-video",
        json={
            "supplier": "google",
            "visualPrompt": "cat on motorbike",
            "narrationScript": "A cat rides fast.",
            "aspectRatio": "16:9",
            "seconds": 4,
        },
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["jobId"]

    job_response = client.get(f"/visiondirector/api/render-jobs/{payload['jobId']}")
    assert job_response.status_code == 200
    job = job_response.get_json()["job"]
    assert job["status"] == "error"
    assert "provider video failure" in job["error"]

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, supplier, status, model, error FROM visiondirector_render_jobs"
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][2] == "error"
    assert rows[0][3] == "veo-3.1-generate-preview"


def test_render_jobs_list_endpoint_reads_sqlite(tmp_path):
    db_path = (
        tmp_path
        / "plugins"
        / "visiondirector"
        / "data"
        / "smx_visiondirector_dev.db"
    )
    storage = build_sqlite_storage(db_path)
    storage.initialize()

    store = SQLiteRenderJobStore(storage)
    store.create(
        job_id="job-list-test",
        supplier="google",
        prompt="list me",
        model="veo-test",
    )

    app = Flask(__name__)
    init_visiondirector(app, project_root=tmp_path, storage=storage)

    response = app.test_client().get("/visiondirector/api/render-jobs")
    assert response.status_code == 200
    assert "job-list-test" in response.get_data(as_text=True)
