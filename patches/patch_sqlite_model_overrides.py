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

if "class SQLiteModelOverridesStore" not in storage:
    storage += dedent(
        r'''

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
        '''
    )
    print("added SQLite model override store")
else:
    print("SQLite model override store already present")

storage_file.write_text(storage, encoding="utf-8")


content = init_file.read_text(encoding="utf-8")

if "SQLiteModelOverridesStore" not in content.split("\n", 40)[0:]:
    content = content.replace(
        "from .storage import build_storage_from_database_url",
        "from .storage import SQLiteModelOverridesStore, VisionDirectorStorage, build_storage_from_database_url",
        1,
    )

if "storage: VisionDirectorStorage | None = None" not in content:
    content = re.sub(
        r"(def create_visiondirector_blueprint\([\s\S]*?usage_recorder: UsageRecorder \| None = None,\n)(\s*\):)",
        r"\1    storage: VisionDirectorStorage | None = None,\n\2",
        content,
        count=1,
    )
    content = re.sub(
        r"(def init_visiondirector\([\s\S]*?usage_recorder: UsageRecorder \| None = None,\n)(\s*\):)",
        r"\1    storage: VisionDirectorStorage | None = None,\n\2",
        content,
        count=1,
    )
    print("added storage parameters")

if "resolved_storage = storage" not in content:
    marker = "    profile_registry = AIProfileRegistry(ai_profile)\n"
    if marker not in content:
        raise SystemExit("Could not find profile_registry marker.")
    insert = '''    resolved_storage = storage
    if resolved_storage is None:
        resolved_storage = build_storage_from_database_url(
            str(resolved_config.get("SMX_VISIONDIRECTOR_DATABASE_URL") or ""),
            fallback_sqlite_path=resolved_project_root
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db",
        )
        resolved_storage.initialize()

'''
    content = content.replace(marker, marker + insert, 1)
    print("created resolved_storage inside blueprint")
else:
    print("resolved_storage already present")

content = content.replace(
    'model_overrides_store = {"google": {}, "openai": {}}',
    "model_overrides_store = SQLiteModelOverridesStore(resolved_storage)",
)

content = content.replace(
    "            usage_recorder=usage_recorder,\n        ),",
    "            usage_recorder=usage_recorder,\n            storage=storage,\n        ),",
    1,
)

content = content.replace(
    "        usage_recorder=usage_recorder,\n    )",
    "        usage_recorder=usage_recorder,\n        storage=storage,\n    )",
    1,
)

init_file.write_text(content, encoding="utf-8")


write_file(
    "tests/test_sqlite_model_overrides.py",
    """
    from __future__ import annotations

    import sqlite3

    from flask import Flask

    from smx_visiondirector import init_visiondirector, setup_visiondirector
    from smx_visiondirector.storage import SQLiteModelOverridesStore, build_sqlite_storage


    def test_sqlite_model_override_store_persists_across_instances(tmp_path):
        db_path = (
            tmp_path
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db"
        )
        storage = build_sqlite_storage(db_path)
        storage.initialize()

        store = SQLiteModelOverridesStore(storage)
        store["google"]["VIDEO_GEN"] = "veo-db-test-model"

        fresh_store = SQLiteModelOverridesStore(build_sqlite_storage(db_path))

        assert fresh_store["google"]["VIDEO_GEN"] == "veo-db-test-model"
        assert fresh_store["google"].get("VIDEO_GEN") == "veo-db-test-model"
        assert dict(fresh_store["google"].items())["VIDEO_GEN"] == "veo-db-test-model"


    def test_model_map_uses_sqlite_backed_overrides(tmp_path):
        db_path = (
            tmp_path
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db"
        )
        storage = build_sqlite_storage(db_path)
        storage.initialize()

        store = SQLiteModelOverridesStore(storage)
        store["google"]["VIDEO_GEN"] = "veo-from-sqlite"

        app = Flask(__name__)
        init_visiondirector(app, project_root=tmp_path, storage=storage)

        response = app.test_client().get("/visiondirector/api/model-map/google")

        assert response.status_code == 200
        assert "veo-from-sqlite" in response.get_data(as_text=True)


    def test_setup_visiondirector_model_override_table_is_real_sqlite_table(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(app, project_root=tmp_path)

        db_path = (
            tmp_path
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db"
        )
        assert db_path.exists()

        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='visiondirector_model_overrides'"
            ).fetchone()

        assert row is not None
    """,
)

print("Patch complete: model overrides now have a SQLite-backed store.")
