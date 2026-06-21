from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
target = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not target.exists():
    raise SystemExit("Missing src/smx_visiondirector/__init__.py. Run from VisionDirector root.")


content = target.read_text(encoding="utf-8")

content = content.replace(
    "from flask import Blueprint, Response, send_from_directory, url_for",
    "from flask import Blueprint, Response, jsonify, request, send_from_directory, url_for",
)

content = content.replace(
    "from typing import Any",
    "from typing import Any\n    from uuid import uuid4",
)

content = content.replace(
    "        bp = Blueprint(\"smx_visiondirector\", __name__)\n",
    """        bp = Blueprint("smx_visiondirector", __name__)

        settings_store = {
            "supplier": "google",
            "ui_scale": "normal",
            "theme": "dark",
        }
        model_overrides_store: dict[str, dict[str, str]] = {
            "google": {},
            "openai": {},
        }
        voice_identities_store: dict[str, list[dict[str, Any]]] = {
            "google": [],
            "openai": [],
        }

""",
)

content = content.replace(
    """        @bp.get("/assets/<path:filename>")
        def asset(filename: str):
""",
    """        @bp.get("/api/credentials/status")
        def credentials_status():
            return {
                "status": {
                    "google": _profile_has_supplier(ai_profile, "google"),
                    "openai": _profile_has_supplier(ai_profile, "openai"),
                },
                "hostManaged": True,
            }


        @bp.route("/api/credentials/<supplier>", methods=["GET", "POST", "DELETE"])
        def credentials_supplier(supplier: str):
            supplier = supplier.strip().lower()
            if supplier not in {"google", "openai"}:
                return {"error": "unsupported supplier"}, 404

            if request.method == "GET":
                return {
                    "supplier": supplier,
                    "available": _profile_has_supplier(ai_profile, supplier),
                    "apiKey": "",
                    "hostManaged": True,
                }

            return {
                "ok": False,
                "hostManaged": True,
                "message": "Credentials are owned by the SyntaxMatrix host and are not stored by the browser plugin.",
            }, 409


        @bp.route("/api/settings/supplier", methods=["GET", "POST"])
        def setting_supplier():
            if request.method == "POST":
                payload = request.get_json(silent=True) or {}
                supplier = str(payload.get("supplier") or "").strip().lower()
                if supplier not in {"google", "openai"}:
                    return {"error": "unsupported supplier"}, 400
                settings_store["supplier"] = supplier
            return {"supplier": settings_store["supplier"]}


        @bp.route("/api/settings/ui-scale", methods=["GET", "POST"])
        def setting_ui_scale():
            if request.method == "POST":
                payload = request.get_json(silent=True) or {}
                ui_scale = str(payload.get("uiScale") or "").strip().lower()
                if ui_scale not in {"normal", "large"}:
                    return {"error": "unsupported uiScale"}, 400
                settings_store["ui_scale"] = ui_scale
            return {"uiScale": settings_store["ui_scale"]}


        @bp.route("/api/settings/theme", methods=["GET", "POST"])
        def setting_theme():
            if request.method == "POST":
                payload = request.get_json(silent=True) or {}
                theme = str(payload.get("theme") or "").strip().lower()
                if theme not in {"dark", "light"}:
                    return {"error": "unsupported theme"}, 400
                settings_store["theme"] = theme
            return {"theme": settings_store["theme"]}


        @bp.get("/api/model-overrides/<supplier>")
        def model_overrides_get(supplier: str):
            supplier = supplier.strip().lower()
            registry = _load_model_registry(resolved_project_root)
            defaults = (
                registry.get("suppliers", {})
                .get(supplier, {})
                .get("defaults", {})
            )
            keys = registry.get("agencies", sorted(defaults))
            return {
                "supplier": supplier,
                "defaults": defaults,
                "keys": keys,
                "overrides": model_overrides_store.setdefault(supplier, {}),
            }


        @bp.post("/api/model-overrides/<supplier>")
        def model_overrides_post(supplier: str):
            supplier = supplier.strip().lower()
            payload = request.get_json(silent=True) or {}
            overrides = payload.get("overrides") or {}
            if not isinstance(overrides, dict):
                return {"error": "overrides must be an object"}, 400

            clean = {
                str(key): str(value).strip()
                for key, value in overrides.items()
                if str(value).strip()
            }
            model_overrides_store[supplier] = clean
            return {"supplier": supplier, "overrides": clean}


        @bp.post("/api/model-overrides/<supplier>/reset")
        def model_overrides_reset(supplier: str):
            supplier = supplier.strip().lower()
            model_overrides_store[supplier] = {}
            return {"supplier": supplier, "overrides": {}}


        @bp.route("/api/voice-identities/<supplier>", methods=["GET", "POST"])
        def voice_identities(supplier: str):
            supplier = supplier.strip().lower()
            if supplier not in voice_identities_store:
                voice_identities_store[supplier] = []

            if request.method == "GET":
                return {"supplier": supplier, "voices": voice_identities_store[supplier]}

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


        @bp.get("/assets/<path:filename>")
        def asset(filename: str):
""",
)

content = content.replace(
    """        @bp.get("/<path:filename>")
        def static_file(filename: str):
            return send_from_directory(resolved_project_root, filename)

        return bp
""",
    """        @bp.get("/<path:filename>")
        def static_file(filename: str):
            if filename == "index.js":
                js_file = resolved_project_root / "index.js"
                if not js_file.exists():
                    return Response("VisionDirector index.js not found.", status=500)
                js = js_file.read_text(encoding="utf-8")
                js = _rewrite_runtime_js_urls(js)
                return Response(js, mimetype="application/javascript")

            return send_from_directory(resolved_project_root, filename)

        return bp
""",
)

content = content.replace(
    """
    def _rewrite_index_asset_urls(html: str) -> str:
""",
    """
    def _profile_has_supplier(
        ai_profile: dict[str, Any] | None,
        supplier: str,
    ) -> bool:
        profile = ai_profile or {}
        supplier = supplier.strip().lower()

        for value in profile.values():
            if isinstance(value, dict) and str(value.get("provider") or "").lower() == supplier:
                return True

        direct = profile.get(supplier)
        return isinstance(direct, dict)


    def _load_model_registry(project_root: Path) -> dict[str, Any]:
        registry_file = project_root / "shared" / "model_registry.json"
        if not registry_file.exists():
            return {
                "agencies": [],
                "suppliers": {},
            }

        try:
            return json.loads(registry_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "agencies": [],
                "suppliers": {},
            }


    def _rewrite_runtime_js_urls(js: str) -> str:
        return (
            js.replace('"/api/', '"/visiondirector/api/')
            .replace("'/api/", "'/visiondirector/api/")
            .replace("`/api/", "`/visiondirector/api/")
        )


    def _rewrite_index_asset_urls(html: str) -> str:
""",
)

target.write_text(content, encoding="utf-8")

tests = ROOT / "tests" / "test_smx_visiondirector_runtime_api.py"
tests.write_text(
    '''from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


def test_index_js_rewrites_root_api_calls_under_plugin_namespace(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert 'fetch("/visiondirector/api/credentials/status"' in body
    assert 'fetch("/api/credentials/status"' not in body
    assert "`/visiondirector/api/model-overrides/${supplier}`" in body


def test_credentials_status_reflects_host_profile(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {"provider": "google", "api_key": "SECRET_GOOGLE"},
            "assistant": {"provider": "openai", "api_key": "SECRET_OPENAI"},
        },
    )

    response = app.test_client().get("/visiondirector/api/credentials/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": {"google": True, "openai": True},
        "hostManaged": True,
    }


def test_credentials_endpoint_never_returns_api_key_value(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={"main": {"provider": "google", "api_key": "SECRET_GOOGLE"}},
    )

    response = app.test_client().get("/visiondirector/api/credentials/google")

    assert response.status_code == 200
    assert response.get_json()["apiKey"] == ""
    assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


def test_settings_runtime_api_round_trip(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)
    client = app.test_client()

    response = client.post(
        "/visiondirector/api/settings/theme",
        json={"theme": "light"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"theme": "light"}

    response = client.get("/visiondirector/api/settings/theme")
    assert response.status_code == 200
    assert response.get_json() == {"theme": "light"}


def test_model_overrides_runtime_api_reads_registry_defaults(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/api/model-overrides/google")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["supplier"] == "google"
    assert "SCRIPT_PARSER" in payload["keys"]
    assert "SCRIPT_PARSER" in payload["defaults"]


def test_voice_identities_runtime_api_round_trip(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)
    client = app.test_client()

    created = client.post(
        "/visiondirector/api/voice-identities/google",
        json={"label": "Narrator", "baseVoice": "Zephyr", "traits": "warm"},
    )

    assert created.status_code == 200
    voice = created.get_json()["voice"]
    assert voice["label"] == "NARRATOR"

    listed = client.get("/visiondirector/api/voice-identities/google")
    assert listed.status_code == 200
    assert listed.get_json()["voices"][0]["id"] == voice["id"]

    deleted = client.delete(f"/visiondirector/api/voice-identities/google/{voice['id']}")
    assert deleted.status_code == 200

    listed = client.get("/visiondirector/api/voice-identities/google")
    assert listed.get_json()["voices"] == []
''',
    encoding="utf-8",
)

print("Patch complete: VisionDirector runtime browser API is now namespaced under /visiondirector/api.")
