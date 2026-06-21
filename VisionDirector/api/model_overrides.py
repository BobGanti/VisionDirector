# api/model_overrides.py
from flask import Blueprint, jsonify, request

from data.model_registry import (
    init_db,
    get_registry_view,
    upsert_overrides,
    reset_overrides,
    normalise_supplier,
    get_saved_supplier,
    save_supplier,
    get_saved_theme,
    save_theme,
    get_setting,
    set_setting,
)


from data.voice_identities import (
    init_voice_db,
    list_voice_identities,
    create_voice_identity,
    delete_voice_identity,
)

from data.credentials import (
    init_credentials_db,
    credentials_status,
    set_api_key,
    delete_api_key,
    get_api_key,
)

# Ensure tables exist on import
init_db()
init_voice_db()
init_credentials_db()

bp = Blueprint("model_overrides", __name__)

@bp.get("/api/settings/supplier")
def get_supplier_setting():
    try:
        return jsonify({"supplier": get_saved_supplier(default="google")})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.post("/api/settings/supplier")
def set_supplier_setting():
    try:
        payload = request.get_json(silent=True) or {}
        supplier = payload.get("supplier") or ""
        supplier = save_supplier(supplier)
        return jsonify({"supplier": supplier})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.get("/api/settings/theme")
def get_theme_setting():
    try:
        return jsonify({"theme": get_saved_theme(default="dark")})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.post("/api/settings/theme")
def set_theme_setting():
    try:
        payload = request.get_json(silent=True) or {}
        theme = payload.get("theme") or ""
        theme = save_theme(theme)
        return jsonify({"theme": theme})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.get("/api/settings/ui-scale")
def get_ui_scale():
    try:
        # default: normal
        scale = (get_setting("ui_scale") or "normal").strip().lower()
        if scale not in ("normal", "large"):
            scale = "normal"
        return jsonify({"uiScale": scale})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.post("/api/settings/ui-scale")
def set_ui_scale():
    try:
        payload = request.get_json(silent=True) or {}
        scale = (payload.get("uiScale") or "").strip().lower()
        if scale not in ("normal", "large"):
            return jsonify({"error": "INVALID_UI_SCALE"}), 400
        set_setting("ui_scale", scale)
        return jsonify({"uiScale": scale})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/api/credentials/status")
def get_credentials_status():
    try:
        return jsonify({"status": credentials_status()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.post("/api/credentials/<supplier>")
def save_credential(supplier: str):
    try:
        payload = request.get_json(silent=True) or {}
        api_key = payload.get("apiKey") or payload.get("api_key") or ""
        set_api_key(supplier, api_key)
        return jsonify({"ok": True, "status": credentials_status()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.delete("/api/credentials/<supplier>")
def remove_credential(supplier: str):
    try:
        delete_api_key(supplier)
        return jsonify({"ok": True, "status": credentials_status()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/api/credentials/<supplier>")
def fetch_credential(supplier: str):
    """
    Used internally by the frontend services to run generation without localStorage.
    Do NOT display this value in the UI.
    """
    try:
        return jsonify({"supplier": supplier, "apiKey": get_api_key(supplier)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/api/model-overrides/<supplier>")
def get_overrides(supplier: str):
    try:
        supplier = normalise_supplier(supplier)
        keys, defaults, overrides = get_registry_view(supplier)
        return jsonify({
            "supplier": supplier,
            "keys": keys,
            "defaults": defaults,
            "overrides": overrides,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.post("/api/model-overrides/<supplier>")
def save_overrides(supplier: str):
    try:
        supplier = normalise_supplier(supplier)
        payload = request.get_json(silent=True) or {}
        overrides = payload.get("overrides") or {}
        upsert_overrides(supplier, overrides)
        keys, defaults, overrides = get_registry_view(supplier)
        return jsonify({
            "supplier": supplier,
            "keys": keys,
            "defaults": defaults,
            "overrides": overrides,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.post("/api/model-overrides/<supplier>/reset")
def reset_supplier(supplier: str):
    try:
        supplier = normalise_supplier(supplier)
        reset_overrides(supplier)
        keys, defaults, overrides = get_registry_view(supplier)
        return jsonify({
            "supplier": supplier,
            "keys": keys,
            "defaults": defaults,
            "overrides": overrides,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.get("/api/voice-identities/<supplier>")
def get_voice_identities(supplier: str):
    try:
        supplier = normalise_supplier(supplier)
        return jsonify({
            "supplier": supplier,
            "voices": list_voice_identities(supplier),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.post("/api/voice-identities/<supplier>")
def post_voice_identity(supplier: str):
    try:
        supplier = normalise_supplier(supplier)
        payload = request.get_json(silent=True) or {}
        voice = create_voice_identity(
            supplier=supplier,
            label=payload.get("label") or "",
            base_voice=payload.get("baseVoice") or payload.get("base_voice") or "",
            traits=payload.get("traits") or "",
            speed=payload.get("speed") or "natural",
            sentiment=payload.get("sentiment"),
        )
        return jsonify({"supplier": supplier, "voice": voice})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.delete("/api/voice-identities/<supplier>/<voice_id>")
def delete_voice_identity_route(supplier: str, voice_id: str):
    try:
        supplier = normalise_supplier(supplier)
        delete_voice_identity(supplier, voice_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
