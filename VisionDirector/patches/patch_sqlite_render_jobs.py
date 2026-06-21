from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
storage_file = ROOT / "src" / "smx_visiondirector" / "storage.py"
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not storage_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/storage.py")
if not init_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/__init__.py")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


storage = storage_file.read_text(encoding="utf-8")

if "class SQLiteRenderJobStore" not in storage:
    storage += dedent(
        r'''

        class SQLiteRenderJobStore:
            """Render job persistence backed by visiondirector_render_jobs."""

            def __init__(self, storage: VisionDirectorStorage):
                self.storage = storage

            def create(
                self,
                *,
                job_id: str,
                supplier: str,
                prompt: str,
                model: str | None,
                status: str = "running",
            ) -> dict[str, Any]:
                sqlite_path = _require_sqlite_storage(self.storage)
                sqlite_path.parent.mkdir(parents=True, exist_ok=True)
                self.storage.initialize()

                clean = {
                    "id": str(job_id or "").strip(),
                    "supplier": str(supplier or "").strip().lower(),
                    "status": str(status or "running").strip().lower(),
                    "prompt": str(prompt or ""),
                    "model": str(model or "") or None,
                    "video_url": None,
                    "video_ref": {},
                    "error": None,
                }

                if not clean["id"]:
                    raise ValueError("render job id is required")
                if not clean["supplier"]:
                    raise ValueError("render job supplier is required")

                with sqlite3.connect(sqlite_path) as conn:
                    conn.execute(
                        "INSERT INTO visiondirector_render_jobs "
                        "(id, supplier, status, prompt, model, video_url, video_ref_json, error, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, NULL, '{}', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                        (
                            clean["id"],
                            clean["supplier"],
                            clean["status"],
                            clean["prompt"],
                            clean["model"],
                        ),
                    )
                    conn.commit()

                return clean

            def mark_success(
                self,
                *,
                job_id: str,
                video_url: str,
                video_ref: dict[str, Any] | None = None,
            ) -> None:
                sqlite_path = _require_sqlite_storage(self.storage)
                with sqlite3.connect(sqlite_path) as conn:
                    conn.execute(
                        "UPDATE visiondirector_render_jobs "
                        "SET status = 'success', video_url = ?, video_ref_json = ?, error = NULL, updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?",
                        (
                            str(video_url or ""),
                            dumps_json(video_ref or {}),
                            str(job_id or "").strip(),
                        ),
                    )
                    conn.commit()

            def mark_error(self, *, job_id: str, error: str) -> None:
                sqlite_path = _require_sqlite_storage(self.storage)
                with sqlite3.connect(sqlite_path) as conn:
                    conn.execute(
                        "UPDATE visiondirector_render_jobs "
                        "SET status = 'error', error = ?, updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?",
                        (
                            str(error or ""),
                            str(job_id or "").strip(),
                        ),
                    )
                    conn.commit()

            def get(self, job_id: str) -> dict[str, Any] | None:
                sqlite_path = _require_sqlite_storage(self.storage)
                if not sqlite_path.exists():
                    return None

                with sqlite3.connect(sqlite_path) as conn:
                    row = conn.execute(
                        "SELECT id, supplier, status, prompt, model, video_url, video_ref_json, error, created_at, updated_at "
                        "FROM visiondirector_render_jobs WHERE id = ?",
                        (str(job_id or "").strip(),),
                    ).fetchone()

                return _render_job_row_to_dict(row) if row else None

            def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
                sqlite_path = _require_sqlite_storage(self.storage)
                if not sqlite_path.exists():
                    return []

                clean_limit = max(1, min(int(limit or 50), 200))

                with sqlite3.connect(sqlite_path) as conn:
                    rows = conn.execute(
                        "SELECT id, supplier, status, prompt, model, video_url, video_ref_json, error, created_at, updated_at "
                        "FROM visiondirector_render_jobs "
                        "ORDER BY updated_at DESC, created_at DESC, id DESC "
                        "LIMIT ?",
                        (clean_limit,),
                    ).fetchall()

                return [_render_job_row_to_dict(row) for row in rows]


        def _render_job_row_to_dict(row) -> dict[str, Any]:
            return {
                "id": str(row[0]),
                "supplier": str(row[1]),
                "status": str(row[2]),
                "prompt": row[3],
                "model": row[4],
                "videoUrl": row[5],
                "videoRef": loads_json(row[6]),
                "error": row[7],
                "createdAt": row[8],
                "updatedAt": row[9],
            }
        '''
    )
    print("added SQLiteRenderJobStore")
else:
    print("SQLiteRenderJobStore already present")

storage_file.write_text(storage, encoding="utf-8")


content = init_file.read_text(encoding="utf-8")

content = re.sub(
    r"from \.storage import SQLiteModelOverridesStore, SQLiteVoiceIdentityStore, VisionDirectorStorage, build_storage_from_database_url",
    "from .storage import SQLiteModelOverridesStore, SQLiteRenderJobStore, SQLiteVoiceIdentityStore, VisionDirectorStorage, build_storage_from_database_url",
    content,
    count=1,
)

if "render_jobs_store = SQLiteRenderJobStore(resolved_storage)" not in content:
    marker = "    voice_identities_store = SQLiteVoiceIdentityStore(resolved_storage)\n"
    if marker not in content:
        raise SystemExit("Could not find voice_identities_store marker.")
    content = content.replace(
        marker,
        marker + "    render_jobs_store = SQLiteRenderJobStore(resolved_storage)\n",
        1,
    )
    print("added render_jobs_store")
else:
    print("render_jobs_store already present")

if '@bp.get("/api/render-jobs")' not in content:
    marker = '    @bp.post("/api/ai/generate-video")\n'
    if marker not in content:
        raise SystemExit("Could not find generate-video route marker.")

    routes = dedent(
        '''
            @bp.get("/api/render-jobs")
            def render_jobs_list():
                limit = request.args.get("limit", 50)
                return {
                    "jobs": render_jobs_store.list(limit=int(limit or 50)),
                }


            @bp.get("/api/render-jobs/<job_id>")
            def render_jobs_get(job_id: str):
                job = render_jobs_store.get(job_id)
                if not job:
                    return {"error": "render job not found"}, 404
                return {"job": job}


        '''
    )
    content = content.replace(marker, routes + marker, 1)
    print("added render job API routes")
else:
    print("render job API routes already present")

# Patch generate-video route with job create/success/error.
if "job_id = uuid4().hex" not in content:
    model_block = '''        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("VIDEO_GEN", supplier)
        )

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        try:
            result = build_ai_runtime(
                profile_registry,
                usage_recorder=resolved_usage_recorder,
            ).generate_video_for_provider(
'''

    replacement = '''        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("VIDEO_GEN", supplier)
        )
        job_id = uuid4().hex

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        render_jobs_store.create(
            job_id=job_id,
            supplier=supplier,
            prompt=visual_prompt,
            model=model,
            status="running",
        )

        try:
            result = build_ai_runtime(
                profile_registry,
                usage_recorder=resolved_usage_recorder,
            ).generate_video_for_provider(
'''

    if model_block not in content:
        raise SystemExit("Could not find generate-video model/try block.")
    content = content.replace(model_block, replacement, 1)

    content = content.replace(
        '''        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "url": result.video_url,
            "videoRef": result.video_ref,
            "supplier": result.provider,
            "model": result.model,
        }
''',
        '''        except VisionDirectorAIProfileError as exc:
            render_jobs_store.mark_error(job_id=job_id, error=str(exc))
            return {"error": str(exc), "jobId": job_id}, 503
        except VisionDirectorAIExecutionError as exc:
            render_jobs_store.mark_error(job_id=job_id, error=str(exc))
            return {"error": str(exc), "jobId": job_id}, 502

        render_jobs_store.mark_success(
            job_id=job_id,
            video_url=result.video_url,
            video_ref=result.video_ref,
        )

        return {
            "url": result.video_url,
            "videoRef": result.video_ref,
            "supplier": result.provider,
            "model": result.model,
            "jobId": job_id,
        }
''',
        1,
    )

    print("patched generate-video route with render job logging")
else:
    print("generate-video route already has render job logging")

init_file.write_text(content, encoding="utf-8")


write_file(
    "tests/test_sqlite_render_jobs.py",
    """
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
        assert success["videoUrl"] == "data:video/mp4;base64,abc"
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
    """,
)

print("Patch complete: video render jobs are now SQLite-backed.")
