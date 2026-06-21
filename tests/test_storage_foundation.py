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
