from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
storage_file = ROOT / "src" / "smx_visiondirector" / "storage.py"
test_file = ROOT / "tests" / "test_render_jobs_do_not_expose_video_payloads.py"

content = storage_file.read_text(encoding="utf-8")

if "def _is_large_video_data_url(" not in content:
    marker = "class SQLiteRenderJobStore"
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find SQLiteRenderJobStore insertion point in storage.py")

    helper = dedent(
        '''
        def _is_large_video_data_url(value: object) -> bool:
            return isinstance(value, str) and value.startswith("data:video/")


        def _safe_video_url_for_job_storage(value: object) -> str | None:
            if _is_large_video_data_url(value):
                return None
            return str(value) if value else None


        def _safe_video_ref_for_job_storage(video_ref: object, video_url: object) -> dict[str, object]:
            if isinstance(video_ref, dict):
                ref = dict(video_ref)
            elif video_ref:
                ref = {"value": str(video_ref)}
            else:
                ref = {}

            if _is_large_video_data_url(video_url):
                ref.setdefault("storage", "not_persisted")
                ref.setdefault("reason", "large_video_data_url")
                ref.setdefault("videoUrlLength", len(str(video_url)))
                ref.setdefault("mediaType", str(video_url).split(";", 1)[0].replace("data:", "", 1))
            return ref


        '''
    ).lstrip()

    content = content[:idx] + helper + content[idx:]
    print("added safe render-job video payload helpers")
else:
    print("safe render-job video payload helpers already present")


start = content.find("    def mark_success(self, job_id: str, video_url: str | None, video_ref: object) -> None:")
if start < 0:
    raise SystemExit("Could not find SQLiteRenderJobStore.mark_success.")

end = content.find("\n    def mark_error(", start)
if end < 0:
    raise SystemExit("Could not find mark_error after mark_success.")

replacement = dedent(
    '''
        def mark_success(self, job_id: str, video_url: str | None, video_ref: object) -> None:
            safe_video_url = _safe_video_url_for_job_storage(video_url)
            safe_video_ref = _safe_video_ref_for_job_storage(video_ref, video_url)

            with self.storage.connect() as conn:
                conn.execute(
                    """
                    UPDATE visiondirector_render_jobs
                    SET status = ?,
                        video_url = ?,
                        video_ref_json = ?,
                        error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        "success",
                        safe_video_url,
                        _dumps_json(safe_video_ref),
                        job_id,
                    ),
                )
                conn.commit()

    '''
)

content = content[:start] + replacement + content[end:]
storage_file.write_text(content, encoding="utf-8")
print("patched SQLiteRenderJobStore.mark_success")


test_file.write_text(
    dedent(
        '''
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
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("added render-job payload safety tests")
