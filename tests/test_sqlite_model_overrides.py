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
