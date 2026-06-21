from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
storage_file = ROOT / "src" / "smx_visiondirector" / "storage.py"

content = storage_file.read_text(encoding="utf-8")

# Ensure safe helpers exist at module level before SQLiteRenderJobStore.
if "def _is_large_video_data_url(" not in content:
    marker = "class SQLiteRenderJobStore:"
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find SQLiteRenderJobStore.")

    helpers = dedent(
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

    content = content[:idx] + helpers + content[idx:]
    print("added safe render-job helpers")
else:
    print("safe render-job helpers already present")

start = content.find("class SQLiteRenderJobStore:")
if start < 0:
    raise SystemExit("Could not find SQLiteRenderJobStore start.")

end = content.find("\ndef _render_job_row_to_dict", start)
if end < 0:
    raise SystemExit("Could not find _render_job_row_to_dict after SQLiteRenderJobStore.")

replacement = dedent(
    '''
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
            safe_video_url = _safe_video_url_for_job_storage(video_url)
            safe_video_ref = _safe_video_ref_for_job_storage(video_ref or {}, video_url)

            with sqlite3.connect(sqlite_path) as conn:
                conn.execute(
                    "UPDATE visiondirector_render_jobs "
                    "SET status = 'success', video_url = ?, video_ref_json = ?, error = NULL, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (
                        safe_video_url,
                        dumps_json(safe_video_ref),
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


    '''
).lstrip()

content = content[:start] + replacement + content[end:]
storage_file.write_text(content, encoding="utf-8")

print("Repaired SQLiteRenderJobStore class.")
