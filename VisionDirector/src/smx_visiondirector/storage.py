from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VisionDirectorStorageConfig:
    database_url: str
    sqlite_path: Path | None
    backend: str


class VisionDirectorStorage:
    """VisionDirector plugin-owned storage.

    Local development uses SQLite under the host plugin folder:
        plugins/visiondirector/data/smx_visiondirector_dev.db

    Production should be wired to a host-managed PostgreSQL database URL
    in a later patch. Provider secrets remain host-owned and are not stored
    here.
    """

    def __init__(self, config: VisionDirectorStorageConfig):
        self.config = config

    @property
    def backend(self) -> str:
        return self.config.backend

    @property
    def sqlite_path(self) -> Path | None:
        return self.config.sqlite_path

    def initialize(self) -> None:
        if self.config.backend != "sqlite":
            raise NotImplementedError(
                "VisionDirector PostgreSQL storage contract exists, but the "
                "PostgreSQL adapter has not been wired in this patch."
            )

        if self.config.sqlite_path is None:
            raise ValueError("sqlite_path is required for SQLite storage")

        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.config.sqlite_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            _create_schema(conn)
            conn.commit()

    def table_names(self) -> set[str]:
        if self.config.backend != "sqlite" or self.config.sqlite_path is None:
            return set()

        if not self.config.sqlite_path.exists():
            return set()

        with sqlite3.connect(self.config.sqlite_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return {str(row[0]) for row in rows}

    def schema_version(self) -> int:
        if self.config.backend != "sqlite" or self.config.sqlite_path is None:
            return 0

        if not self.config.sqlite_path.exists():
            return 0

        with sqlite3.connect(self.config.sqlite_path) as conn:
            row = conn.execute(
                "SELECT version FROM visiondirector_schema_migrations "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
        return int(row[0]) if row else 0

    def storage_status(self) -> dict[str, Any]:
        return {
            "backend": self.config.backend,
            "databaseUrl": self.config.database_url,
            "sqlitePath": str(self.config.sqlite_path) if self.config.sqlite_path else None,
            "schemaVersion": self.schema_version(),
            "tables": sorted(self.table_names()),
        }


def build_sqlite_storage(sqlite_path: Path) -> VisionDirectorStorage:
    return VisionDirectorStorage(
        VisionDirectorStorageConfig(
            database_url=f"sqlite:///{sqlite_path.as_posix()}",
            sqlite_path=sqlite_path,
            backend="sqlite",
        )
    )


def build_storage_from_database_url(
    database_url: str,
    *,
    fallback_sqlite_path: Path,
) -> VisionDirectorStorage:
    clean = str(database_url or "").strip()

    if not clean:
        return build_sqlite_storage(fallback_sqlite_path)

    if clean.startswith("sqlite:///"):
        return build_sqlite_storage(Path(clean.removeprefix("sqlite:///")))

    if clean.startswith(("postgresql://", "postgres://")):
        return VisionDirectorStorage(
            VisionDirectorStorageConfig(
                database_url=clean,
                sqlite_path=None,
                backend="postgresql",
            )
        )

    raise ValueError(f"Unsupported VisionDirector database URL: {clean}")


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS visiondirector_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS visiondirector_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS visiondirector_model_overrides (
            supplier TEXT NOT NULL,
            task TEXT NOT NULL,
            model TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (supplier, task)
        );

        CREATE TABLE IF NOT EXISTS visiondirector_voice_identities (
            id TEXT PRIMARY KEY,
            supplier TEXT NOT NULL,
            label TEXT NOT NULL,
            base_voice TEXT NOT NULL,
            traits TEXT NOT NULL,
            speed TEXT NOT NULL DEFAULT 'natural',
            sentiment TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS visiondirector_usage_events (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            operation TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT,
            role TEXT,
            status TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            cached_tokens INTEGER NOT NULL DEFAULT 0,
            reasoning_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS visiondirector_render_jobs (
            id TEXT PRIMARY KEY,
            supplier TEXT NOT NULL,
            status TEXT NOT NULL,
            prompt TEXT,
            model TEXT,
            video_url TEXT,
            video_ref_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS visiondirector_assets (
            id TEXT PRIMARY KEY,
            asset_type TEXT NOT NULL,
            url TEXT,
            file_name TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT OR IGNORE INTO visiondirector_schema_migrations(version)
        VALUES (1);
        """
    )


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads_json(value: str | None) -> Any:
    if not value:
        return {}
    return json.loads(value)


class SQLiteSupplierModelOverrides:
    """Mapping-like supplier view backed by visiondirector_model_overrides."""

    def __init__(self, storage: VisionDirectorStorage, supplier: str):
        self.storage = storage
        self.supplier = str(supplier or "").strip().lower()

    def __getitem__(self, task: str) -> str:
        value = self.get(task)
        if value is None:
            raise KeyError(task)
        return value

    def __setitem__(self, task: str, model: str) -> None:
        self.storage.set_model_override(self.supplier, task, model)

    def __delitem__(self, task: str) -> None:
        if not self.storage.delete_model_override(self.supplier, task):
            raise KeyError(task)

    def __contains__(self, task: object) -> bool:
        if not isinstance(task, str):
            return False
        return self.get(task) is not None

    def __iter__(self):
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self.keys())

    def __bool__(self) -> bool:
        return bool(self.keys())

    def get(self, task: str, default=None):
        value = self.storage.get_model_override(self.supplier, task)
        return default if value is None else value

    def keys(self):
        return list(self.to_dict().keys())

    def values(self):
        return list(self.to_dict().values())

    def items(self):
        return list(self.to_dict().items())

    def update(self, values: dict[str, str]) -> None:
        for task, model in dict(values or {}).items():
            self[task] = model

    def clear(self) -> None:
        self.storage.clear_model_overrides(self.supplier)

    def to_dict(self) -> dict[str, str]:
        return self.storage.list_model_overrides(self.supplier)

    def copy(self) -> dict[str, str]:
        return self.to_dict()


class SQLiteModelOverridesStore:
    """Dict-like model override store backed by SQLite."""

    def __init__(self, storage: VisionDirectorStorage):
        self.storage = storage

    def __getitem__(self, supplier: str) -> SQLiteSupplierModelOverrides:
        return SQLiteSupplierModelOverrides(self.storage, supplier)

    def __setitem__(self, supplier: str, overrides: dict[str, str]) -> None:
        supplier = str(supplier or "").strip().lower()
        self.storage.clear_model_overrides(supplier)
        for task, model in dict(overrides or {}).items():
            self.storage.set_model_override(supplier, task, model)

    def __delitem__(self, supplier: str) -> None:
        self.storage.clear_model_overrides(supplier)

    def __contains__(self, supplier: object) -> bool:
        if not isinstance(supplier, str):
            return False
        return bool(self.storage.list_model_overrides(supplier))

    def __iter__(self):
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self.keys())

    def get(self, supplier: str, default=None):
        supplier = str(supplier or "").strip().lower()
        if not supplier:
            return default
        return SQLiteSupplierModelOverrides(self.storage, supplier)

    def keys(self):
        return list(self.storage.list_model_overrides().keys())

    def values(self):
        data = self.storage.list_model_overrides()
        return list(data.values())

    def items(self):
        data = self.storage.list_model_overrides()
        return list(data.items())

    def to_dict(self) -> dict[str, dict[str, str]]:
        return self.storage.list_model_overrides()


def _require_sqlite_storage(storage: VisionDirectorStorage) -> Path:
    if storage.config.backend != "sqlite" or storage.config.sqlite_path is None:
        raise NotImplementedError(
            "SQLite model override store currently requires SQLite storage. "
            "PostgreSQL support will be wired through the production adapter later."
        )
    return storage.config.sqlite_path


def _clean_supplier_task_model(supplier: str, task: str, model: str) -> tuple[str, str, str]:
    clean_supplier = str(supplier or "").strip().lower()
    clean_task = str(task or "").strip().upper()
    clean_model = str(model or "").strip()
    if not clean_supplier:
        raise ValueError("supplier is required")
    if not clean_task:
        raise ValueError("task is required")
    if not clean_model:
        raise ValueError("model is required")
    return clean_supplier, clean_task, clean_model


def _storage_list_model_overrides(
    self: VisionDirectorStorage,
    supplier: str | None = None,
) -> dict[str, Any]:
    _require_sqlite_storage(self)
    if self.config.sqlite_path is None or not self.config.sqlite_path.exists():
        return {}

    with sqlite3.connect(self.config.sqlite_path) as conn:
        if supplier:
            clean_supplier = str(supplier or "").strip().lower()
            rows = conn.execute(
                "SELECT task, model FROM visiondirector_model_overrides "
                "WHERE supplier = ? ORDER BY task",
                (clean_supplier,),
            ).fetchall()
            return {str(task): str(model) for task, model in rows}

        rows = conn.execute(
            "SELECT supplier, task, model FROM visiondirector_model_overrides "
            "ORDER BY supplier, task"
        ).fetchall()

    result: dict[str, dict[str, str]] = {}
    for row_supplier, task, model in rows:
        result.setdefault(str(row_supplier), {})[str(task)] = str(model)
    return result


def _storage_get_model_override(
    self: VisionDirectorStorage,
    supplier: str,
    task: str,
) -> str | None:
    _require_sqlite_storage(self)
    clean_supplier = str(supplier or "").strip().lower()
    clean_task = str(task or "").strip().upper()

    if self.config.sqlite_path is None or not self.config.sqlite_path.exists():
        return None

    with sqlite3.connect(self.config.sqlite_path) as conn:
        row = conn.execute(
            "SELECT model FROM visiondirector_model_overrides "
            "WHERE supplier = ? AND task = ?",
            (clean_supplier, clean_task),
        ).fetchone()
    return str(row[0]) if row else None


def _storage_set_model_override(
    self: VisionDirectorStorage,
    supplier: str,
    task: str,
    model: str,
) -> None:
    sqlite_path = _require_sqlite_storage(self)
    clean_supplier, clean_task, clean_model = _clean_supplier_task_model(
        supplier,
        task,
        model,
    )
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    self.initialize()

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            "INSERT INTO visiondirector_model_overrides "
            "(supplier, task, model, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(supplier, task) DO UPDATE SET "
            "model = excluded.model, updated_at = CURRENT_TIMESTAMP",
            (clean_supplier, clean_task, clean_model),
        )
        conn.commit()


def _storage_delete_model_override(
    self: VisionDirectorStorage,
    supplier: str,
    task: str,
) -> bool:
    _require_sqlite_storage(self)
    clean_supplier = str(supplier or "").strip().lower()
    clean_task = str(task or "").strip().upper()

    if self.config.sqlite_path is None or not self.config.sqlite_path.exists():
        return False

    with sqlite3.connect(self.config.sqlite_path) as conn:
        cur = conn.execute(
            "DELETE FROM visiondirector_model_overrides "
            "WHERE supplier = ? AND task = ?",
            (clean_supplier, clean_task),
        )
        conn.commit()
    return cur.rowcount > 0


def _storage_clear_model_overrides(
    self: VisionDirectorStorage,
    supplier: str | None = None,
) -> None:
    _require_sqlite_storage(self)
    if self.config.sqlite_path is None or not self.config.sqlite_path.exists():
        return

    with sqlite3.connect(self.config.sqlite_path) as conn:
        if supplier:
            conn.execute(
                "DELETE FROM visiondirector_model_overrides WHERE supplier = ?",
                (str(supplier or "").strip().lower(),),
            )
        else:
            conn.execute("DELETE FROM visiondirector_model_overrides")
        conn.commit()


VisionDirectorStorage.list_model_overrides = _storage_list_model_overrides
VisionDirectorStorage.get_model_override = _storage_get_model_override
VisionDirectorStorage.set_model_override = _storage_set_model_override
VisionDirectorStorage.delete_model_override = _storage_delete_model_override
VisionDirectorStorage.clear_model_overrides = _storage_clear_model_overrides


class SQLiteVoiceIdentityStore:
    """Voice identity persistence backed by visiondirector_voice_identities."""

    def __init__(self, storage: VisionDirectorStorage):
        self.storage = storage

    def list(self, supplier: str) -> list[dict[str, Any]]:
        _require_sqlite_storage(self.storage)
        clean_supplier = str(supplier or "").strip().lower()

        if (
            self.storage.config.sqlite_path is None
            or not self.storage.config.sqlite_path.exists()
        ):
            return []

        with sqlite3.connect(self.storage.config.sqlite_path) as conn:
            rows = conn.execute(
                "SELECT id, supplier, label, base_voice, traits, speed, sentiment "
                "FROM visiondirector_voice_identities "
                "WHERE supplier = ? "
                "ORDER BY created_at DESC, id DESC",
                (clean_supplier,),
            ).fetchall()

        return [
            {
                "id": str(row[0]),
                "supplier": str(row[1]),
                "label": str(row[2]),
                "baseVoice": str(row[3]),
                "traits": str(row[4]),
                "speed": str(row[5]),
                "sentiment": row[6],
            }
            for row in rows
        ]

    def create(self, voice: dict[str, Any]) -> dict[str, Any]:
        _require_sqlite_storage(self.storage)
        sqlite_path = self.storage.config.sqlite_path
        if sqlite_path is None:
            raise ValueError("sqlite_path is required for SQLite voice identity storage")

        clean_voice = {
            "id": str(voice.get("id") or "").strip(),
            "supplier": str(voice.get("supplier") or "").strip().lower(),
            "label": str(voice.get("label") or "VOICE").strip().upper(),
            "baseVoice": str(voice.get("baseVoice") or "Zephyr").strip(),
            "traits": str(voice.get("traits") or ""),
            "speed": str(voice.get("speed") or "natural").strip(),
            "sentiment": voice.get("sentiment"),
        }

        if not clean_voice["id"]:
            raise ValueError("voice id is required")
        if not clean_voice["supplier"]:
            raise ValueError("voice supplier is required")

        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage.initialize()

        with sqlite3.connect(sqlite_path) as conn:
            conn.execute(
                "INSERT INTO visiondirector_voice_identities "
                "(id, supplier, label, base_voice, traits, speed, sentiment, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (
                    clean_voice["id"],
                    clean_voice["supplier"],
                    clean_voice["label"],
                    clean_voice["baseVoice"],
                    clean_voice["traits"],
                    clean_voice["speed"],
                    clean_voice["sentiment"],
                ),
            )
            conn.commit()

        return clean_voice

    def delete(self, supplier: str, voice_id: str) -> bool:
        _require_sqlite_storage(self.storage)
        clean_supplier = str(supplier or "").strip().lower()
        clean_id = str(voice_id or "").strip()

        if (
            self.storage.config.sqlite_path is None
            or not self.storage.config.sqlite_path.exists()
        ):
            return False

        with sqlite3.connect(self.storage.config.sqlite_path) as conn:
            cur = conn.execute(
                "DELETE FROM visiondirector_voice_identities "
                "WHERE supplier = ? AND id = ?",
                (clean_supplier, clean_id),
            )
            conn.commit()

        return cur.rowcount > 0


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
