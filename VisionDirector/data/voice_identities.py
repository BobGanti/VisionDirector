# data/voice_identities.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from .db import connect
from .model_registry import normalise_supplier


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def init_voice_db() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS voice_identities (
            id         TEXT PRIMARY KEY,
            supplier   TEXT NOT NULL,
            label      TEXT NOT NULL,
            base_voice TEXT NOT NULL,
            traits     TEXT NOT NULL,
            speed      TEXT NOT NULL,
            sentiment  TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (supplier, label)
        )
        """
    )
    conn.commit()
    conn.close()


def list_voice_identities(supplier: str) -> List[Dict]:
    supplier = normalise_supplier(supplier)
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, supplier, label, base_voice, traits, speed, sentiment, created_at, updated_at
        FROM voice_identities
        WHERE supplier = ?
        ORDER BY updated_at DESC
        """,
        (supplier,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_voice_identity(
    supplier: str,
    label: str,
    base_voice: str,
    traits: str,
    speed: str,
    sentiment: Optional[str] = None,
) -> Dict:
    supplier = normalise_supplier(supplier)

    clean_label = (label or "").strip().upper()
    if not clean_label:
        raise ValueError("LABEL_REQUIRED")

    base_voice = (base_voice or "").strip()
    if not base_voice:
        raise ValueError("BASE_VOICE_REQUIRED")

    traits = (traits or "").strip()
    if not traits:
        raise ValueError("TRAITS_REQUIRED")

    speed = (speed or "").strip()
    if speed not in ("slower", "slow", "natural", "fast", "faster"):
        raise ValueError("INVALID_SPEED")

    if sentiment is not None:
        sentiment = (sentiment or "").strip()
        if sentiment and sentiment not in ("neutral", "cinematic", "aggressive", "whispering", "joyful", "somber"):
            raise ValueError("INVALID_SENTIMENT")

    vid = f"v-{uuid4().hex}"
    now = _now()

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO voice_identities (id, supplier, label, base_voice, traits, speed, sentiment, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vid, supplier, clean_label, base_voice, traits, speed, sentiment or None, now, now),
    )
    conn.commit()
    conn.close()

    return {
        "id": vid,
        "supplier": supplier,
        "label": clean_label,
        "baseVoice": base_voice,
        "traits": traits,
        "speed": speed,
        "sentiment": sentiment or None,
        "created_at": now,
        "updated_at": now,
    }


def delete_voice_identity(supplier: str, voice_id: str) -> None:
    supplier = normalise_supplier(supplier)
    voice_id = (voice_id or "").strip()
    if not voice_id:
        raise ValueError("VOICE_ID_REQUIRED")

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM voice_identities WHERE supplier = ? AND id = ?",
        (supplier, voice_id),
    )
    conn.commit()
    conn.close()

