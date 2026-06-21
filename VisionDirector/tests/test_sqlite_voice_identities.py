from __future__ import annotations

import sqlite3

from flask import Flask

from smx_visiondirector import init_visiondirector, setup_visiondirector
from smx_visiondirector.storage import SQLiteVoiceIdentityStore, build_sqlite_storage


def test_sqlite_voice_identity_store_persists_across_instances(tmp_path):
    db_path = (
        tmp_path
        / "plugins"
        / "visiondirector"
        / "data"
        / "smx_visiondirector_dev.db"
    )
    storage = build_sqlite_storage(db_path)
    storage.initialize()

    store = SQLiteVoiceIdentityStore(storage)
    created = store.create(
        {
            "id": "voice-1",
            "supplier": "google",
            "label": "Narrator",
            "baseVoice": "Zephyr",
            "traits": "Warm, calm",
            "speed": "natural",
            "sentiment": "friendly",
        }
    )

    fresh_store = SQLiteVoiceIdentityStore(build_sqlite_storage(db_path))
    voices = fresh_store.list("google")

    assert created["id"] == "voice-1"
    assert voices[0]["id"] == "voice-1"
    assert voices[0]["baseVoice"] == "Zephyr"
    assert voices[0]["traits"] == "Warm, calm"


def test_voice_identity_api_uses_sqlite_storage_and_delete(tmp_path):
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
    init_visiondirector(app, project_root=tmp_path, storage=storage)
    client = app.test_client()

    create_response = client.post(
        "/visiondirector/api/voice-identities/google",
        json={
            "label": "Soft guide",
            "baseVoice": "Aoede",
            "traits": "Soft, clear",
            "speed": "slow",
            "sentiment": "calm",
        },
    )

    assert create_response.status_code == 200
    created = create_response.get_json()["voice"]

    list_response = client.get("/visiondirector/api/voice-identities/google")
    assert list_response.status_code == 200
    voices = list_response.get_json()["voices"]
    assert voices[0]["id"] == created["id"]
    assert voices[0]["label"] == "SOFT GUIDE"

    delete_response = client.delete(
        f"/visiondirector/api/voice-identities/google/{created['id']}"
    )
    assert delete_response.status_code == 200
    assert delete_response.get_json()["deleted"] is True

    after_delete = client.get("/visiondirector/api/voice-identities/google")
    assert after_delete.get_json()["voices"] == []


def test_setup_visiondirector_voice_identity_table_is_real_sqlite_table(tmp_path):
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
            "WHERE type='table' AND name='visiondirector_voice_identities'"
        ).fetchone()

    assert row is not None
