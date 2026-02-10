# api/model_overrides.py
from flask import Blueprint, jsonify, request

from data.model_registry import (
    init_db,
    get_registry_view,
    upsert_overrides,
    reset_overrides,
    normalise_supplier,
)

bp = Blueprint("model_overrides", __name__)


# Ensure tables exist on import
init_db()

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
