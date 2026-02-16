# data/model_registry.py
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from .db import connect

import json
from pathlib import Path
 


_REG_PATH = Path(__file__).resolve().parents[1] / "shared" / "model_registry.json"


def load_registry():
    if not _REG_PATH.exists():
        raise FileNotFoundError(f"Missing registry file: {_REG_PATH}")
    with _REG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def registry_agencies():
    reg = load_registry()
    return reg.get("agencies", [])

def registry_defaults(supplier: str):
    reg = load_registry()
    return reg.get("suppliers", {}).get(supplier, {}).get("defaults", {})


MODEL_KEYS: List[str] = [
    "SCRIPT_PARSER",
    "DICTATION",
    "VOICE_ANALYZER",
    "AUTO_NARRATOR",
    "IMAGE_GEN",
    "VIDEO_GEN",
    "TTS_PREVIEW",
]

DEFAULT_MODELS: Dict[str, Dict[str, str]] = {
    "google": {
        "SCRIPT_PARSER": "gemini-3-preview",
        "DICTATION": "gemini-3-preview",
        "VOICE_ANALYZER": "gemini-3-preview",
        "AUTO_NARRATOR": "gemini-1.5-pro",
        "IMAGE_GEN": "imagen-3",
        "VIDEO_GEN": "veo-2",
        "TTS_PREVIEW": "gemini-1.5-pro",
    },
    "openai": {
        "SCRIPT_PARSER": "gpt-4.1-mini",
        "DICTATION": "gpt-4.1-mini",
        "VOICE_ANALYZER": "gpt-4.1-mini",
        "AUTO_NARRATOR": "gpt-4.1-mini",
        "IMAGE_GEN": "gpt-image-1",
        "VIDEO_GEN": "sora-2",
        "TTS_PREVIEW": "gpt-4.1-mini",
    },
}

def init_db() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS model_overrides (
            supplier   TEXT NOT NULL,
            model_key  TEXT NOT NULL,
            model_value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (supplier, model_key)
        )
    """)

    # NEW: global app settings (stored in same SQLite file)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def normalise_supplier(supplier: str) -> str:
    s = (supplier or "").strip().lower()
    if s not in ("google", "openai"):
        raise ValueError("INVALID_SUPPLIER")
    return s

def get_registry_view(supplier: str) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    supplier = normalise_supplier(supplier)

    keys = registry_agencies()
    defaults = registry_defaults(supplier)

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT model_key, model_value FROM model_overrides WHERE supplier = ?",
        (supplier,),
    )
    rows = cur.fetchall()
    conn.close()

    overrides: Dict[str, str] = {}
    for r in rows:
        v = (r["model_value"] or "").strip()
        if v:
            overrides[r["model_key"]] = v

    return keys, defaults, overrides


def upsert_overrides(supplier: str, overrides: Dict[str, str]) -> None:
    supplier = normalise_supplier(supplier)
    if not isinstance(overrides, dict):
        raise ValueError("INVALID_OVERRIDES")

    now = datetime.utcnow().isoformat() + "Z"

    conn = connect()
    cur = conn.cursor()

    keys = registry_agencies()
    for k in keys:
        if k not in overrides:
            continue
        v = (overrides.get(k) or "").strip()
        if v:
            cur.execute(
                """
                INSERT INTO model_overrides (supplier, model_key, model_value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(supplier, model_key) DO UPDATE SET
                  model_value = excluded.model_value,
                  updated_at  = excluded.updated_at
                """,
                (supplier, k, v, now),
            )
        else:
            cur.execute(
                "DELETE FROM model_overrides WHERE supplier = ? AND model_key = ?",
                (supplier, k),
            )

    conn.commit()
    conn.close()

def reset_overrides(supplier: str) -> None:
    supplier = normalise_supplier(supplier)
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM model_overrides WHERE supplier = ?", (supplier,))
    conn.commit()
    conn.close()

# -----------------------------
# App settings (global)
# -----------------------------

def get_setting(key: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else None

def set_setting(key: str, value: str) -> None:
    now = datetime.utcnow().isoformat() + "Z"
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          value      = excluded.value,
          updated_at = excluded.updated_at
        """,
        (key, value, now),
    )
    conn.commit()
    conn.close()

SUPPLIER_SETTING_KEY = "supplier"

def get_saved_supplier(default: str = "google") -> str:
    v = get_setting(SUPPLIER_SETTING_KEY)
    if not v:
        return default
    try:
        return normalise_supplier(v)
    except Exception:
        return default

def save_supplier(supplier: str) -> str:
    s = normalise_supplier(supplier)
    set_setting(SUPPLIER_SETTING_KEY, s)
    return s

THEME_SETTING_KEY = "theme"

def normalise_theme(theme: str) -> str:
    t = (theme or "").strip().lower()
    if t not in ("dark", "light"):
        raise ValueError("INVALID_THEME")
    return t

def get_saved_theme(default: str = "dark") -> str:
    v = get_setting(THEME_SETTING_KEY)
    if not v:
        return default
    try:
        return normalise_theme(v)
    except Exception:
        return default

def save_theme(theme: str) -> str:
    t = normalise_theme(theme)
    set_setting(THEME_SETTING_KEY, t)
    return t
