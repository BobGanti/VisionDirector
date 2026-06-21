from __future__ import annotations

from smx_visiondirector.storage import SQLiteRenderJobStore, build_sqlite_storage


def test_render_job_success_does_not_persist_large_base64_video_payload(tmp_path):
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
        job_id="job-large-video",
        supplier="google",
        prompt="cat on motorbike",
        model="veo-3.1-generate-preview",
    )

    video_url = "data:video/mp4;base64," + ("A" * 100_000)
    store.mark_success(
        job_id="job-large-video",
        video_url=video_url,
        video_ref={},
    )

    job = store.get("job-large-video")

    assert job is not None
    assert job["status"] == "success"
    assert job["videoUrl"] is None
    assert job["videoRef"]["storage"] == "not_persisted"
    assert job["videoRef"]["reason"] == "large_video_data_url"
    assert job["videoRef"]["videoUrlLength"] == len(video_url)
    assert job["videoRef"]["mediaType"] == "video/mp4"


def test_render_job_success_can_keep_normal_external_video_url(tmp_path):
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
        job_id="job-external-url",
        supplier="google",
        prompt="cat on motorbike",
        model="veo-3.1-generate-preview",
    )

    store.mark_success(
        job_id="job-external-url",
        video_url="https://example.test/video.mp4",
        video_ref={"provider": "google"},
    )

    job = store.get("job-external-url")

    assert job is not None
    assert job["status"] == "success"
    assert job["videoUrl"] == "https://example.test/video.mp4"
    assert job["videoRef"] == {"provider": "google"}
