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

if "class SQLiteVoiceIdentityStore" not in storage:
    storage += dedent(
        r'''

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
        '''
    )
    print("added SQLiteVoiceIdentityStore")
else:
    print("SQLiteVoiceIdentityStore already present")

storage_file.write_text(storage, encoding="utf-8")


content = init_file.read_text(encoding="utf-8")

content = re.sub(
    r"from \.storage import SQLiteModelOverridesStore, VisionDirectorStorage, build_storage_from_database_url",
    "from .storage import SQLiteModelOverridesStore, SQLiteVoiceIdentityStore, VisionDirectorStorage, build_storage_from_database_url",
    content,
    count=1,
)

content = re.sub(
    r"\n\s*voice_identities_store:\s*dict\[str,\s*list\[dict\[str,\s*Any\]\]\]\s*=\s*\{\s*"
    r'"google":\s*\[\],\s*'
    r'"openai":\s*\[\],\s*'
    r"\}",
    "\n    voice_identities_store = SQLiteVoiceIdentityStore(resolved_storage)",
    content,
    count=1,
    flags=re.MULTILINE,
)

old_route = '''    @bp.route("/api/voice-identities/<supplier>", methods=["GET", "POST"])
    def voice_identities(supplier: str):
        supplier = supplier.strip().lower()
        if supplier not in voice_identities_store:
            voice_identities_store[supplier] = []

        if request.method == "GET":
            return {
                "supplier": supplier,
                "voices": voice_identities_store[supplier],
            }

        payload = request.get_json(silent=True) or {}
        voice = {
            "id": uuid4().hex,
            "supplier": supplier,
            "label": str(payload.get("label") or "VOICE").upper(),
            "baseVoice": str(payload.get("baseVoice") or "Zephyr"),
            "traits": str(payload.get("traits") or ""),
            "speed": str(payload.get("speed") or "natural"),
            "sentiment": payload.get("sentiment"),
        }
        voice_identities_store[supplier].insert(0, voice)

        return {"supplier": supplier, "voice": voice}

    @bp.delete("/api/voice-identities/<supplier>/<voice_id>")
    def voice_identity_delete(supplier: str, voice_id: str):
        supplier = supplier.strip().lower()
        current = voice_identities_store.setdefault(supplier, [])
        voice_identities_store[supplier] = [
            voice for voice in current if voice.get("id") != voice_id
        ]
        return {"ok": True}
'''

new_route = '''    @bp.route("/api/voice-identities/<supplier>", methods=["GET", "POST"])
    def voice_identities(supplier: str):
        supplier = supplier.strip().lower()

        if request.method == "GET":
            return {
                "supplier": supplier,
                "voices": voice_identities_store.list(supplier),
            }

        payload = request.get_json(silent=True) or {}
        voice = voice_identities_store.create(
            {
                "id": uuid4().hex,
                "supplier": supplier,
                "label": str(payload.get("label") or "VOICE").upper(),
                "baseVoice": str(payload.get("baseVoice") or "Zephyr"),
                "traits": str(payload.get("traits") or ""),
                "speed": str(payload.get("speed") or "natural"),
                "sentiment": payload.get("sentiment"),
            }
        )

        return {"supplier": supplier, "voice": voice}

    @bp.delete("/api/voice-identities/<supplier>/<voice_id>")
    def voice_identity_delete(supplier: str, voice_id: str):
        supplier = supplier.strip().lower()
        deleted = voice_identities_store.delete(supplier, voice_id)
        return {"ok": True, "deleted": deleted}
'''

if old_route not in content:
    raise SystemExit("Could not find the current in-memory voice identity route block.")

content = content.replace(old_route, new_route, 1)

init_file.write_text(content, encoding="utf-8")


write_file(
    "tests/test_sqlite_voice_identities.py",
    """
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
    """,
)

print("Patch complete: voice identities now use SQLite storage.")
