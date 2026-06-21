from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
storage_file = ROOT / "src" / "smx_visiondirector" / "storage.py"

if not init_file.exists():
    raise SystemExit("Run from VisionDirector root. Missing src/smx_visiondirector/__init__.py.")
if not storage_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/storage.py. Re-run the first storage patch if needed.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


content = init_file.read_text(encoding="utf-8")

if "from .storage import build_storage_from_database_url" not in content:
    marker = "from .model_router import build_model_router\n"
    if marker not in content:
        raise SystemExit("Could not find model_router import marker.")
    content = content.replace(
        marker,
        marker + "from .storage import build_storage_from_database_url\n",
        1,
    )
    print("inserted storage import")
else:
    print("storage import already present")

old = '    usage_recorder = JsonlUsageRecorder(scaffold.data_dir / "usage_events.jsonl")\n'
new = '''    storage = build_storage_from_database_url(
        config.get("SMX_VISIONDIRECTOR_DATABASE_URL", ""),
        fallback_sqlite_path=scaffold.data_dir / "smx_visiondirector_dev.db",
    )
    storage.initialize()
    usage_recorder = JsonlUsageRecorder(scaffold.data_dir / "usage_events.jsonl")
'''

if 'smx_visiondirector_dev.db' not in content:
    if old not in content:
        raise SystemExit("Could not find usage_recorder setup marker.")
    content = content.replace(old, new, 1)
    print("wired setup_visiondirector to initialize local dev SQLite DB")
else:
    print("local dev SQLite DB initialization already present")

init_file.write_text(content, encoding="utf-8")

write_file(
    "tests/test_storage_foundation.py",
    """
    from __future__ import annotations

    import sqlite3

    from flask import Flask

    from smx_visiondirector import setup_visiondirector
    from smx_visiondirector.storage import build_sqlite_storage


    REQUIRED_TABLES = {
        "visiondirector_schema_migrations",
        "visiondirector_settings",
        "visiondirector_model_overrides",
        "visiondirector_voice_identities",
        "visiondirector_usage_events",
        "visiondirector_render_jobs",
        "visiondirector_assets",
    }


    def test_sqlite_storage_initializes_core_plugin_tables(tmp_path):
        db_path = (
            tmp_path
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db"
        )

        storage = build_sqlite_storage(db_path)
        storage.initialize()

        assert db_path.exists()
        assert storage.schema_version() == 1
        assert REQUIRED_TABLES.issubset(storage.table_names())


    def test_setup_visiondirector_injects_local_dev_db_into_host_plugin_folder(tmp_path):
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
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

        tables = {row[0] for row in rows}
        assert REQUIRED_TABLES.issubset(tables)


    def test_storage_status_does_not_include_provider_secrets(tmp_path):
        db_path = (
            tmp_path
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db"
        )
        storage = build_sqlite_storage(db_path)
        storage.initialize()

        status = storage.storage_status()
        body = str(status).lower()

        assert status["backend"] == "sqlite"
        assert status["schemaVersion"] == 1
        assert "api_key" not in body
        assert "secret" not in body
        assert "password" not in body
    """,
)

print("Patch complete: storage foundation is wired into setup_visiondirector.")
