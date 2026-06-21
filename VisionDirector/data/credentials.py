# data/credentials.py
"""Encrypted API credential storage.

Design goals for VisionDirector:
  - Supplier API keys are NEVER shipped in the image / env vars.
  - Users paste keys in "API Interface Credentials".
  - Keys are encrypted at rest in SQLite.
  - A single master key file lives alongside the SQLite database inside
    data/syntaxmatrixdir/ (bucket-backed in your deployment).

Recovery rule (Option B):
  If the master key file is missing and encrypted credentials exist, we generate
  a new master key and wipe the encrypted credentials (user re-enters keys).

NOTE: There is no user/auth isolation in this app yet, so the credentials are
instance-wide.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from cryptography.fernet import Fernet, InvalidToken

from .db import connect, ensure_db_dir_exists, get_db_path


SUPPORTED = ("google", "openai")
MASTER_KEY_FILENAME = ".vd_master_key"

_LAST_AUTO_RESET: bool = False


def _master_key_path() -> str:
    db_path = Path(get_db_path()).resolve()
    return str(db_path.parent / MASTER_KEY_FILENAME)


def init_credentials_db() -> None:
    c = connect()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS api_credentials (
          supplier   TEXT PRIMARY KEY,
          token      TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    c.commit()
    c.close()


def _credentials_rowcount() -> int:
    c = connect()
    try:
        row = c.execute("SELECT COUNT(*) AS n FROM api_credentials").fetchone()
        return int(row["n"] if row else 0)
    finally:
        c.close()


def _wipe_credentials() -> None:
    c = connect()
    try:
        c.execute("DELETE FROM api_credentials")
        c.commit()
    finally:
        c.close()


def ensure_master_key(reset_credentials_if_missing: bool = True) -> Tuple[bytes, bool]:
    global _LAST_AUTO_RESET
    _LAST_AUTO_RESET = False

    ensure_db_dir_exists()
    init_credentials_db()

    p = Path(_master_key_path())

    if p.exists():
        key = p.read_bytes().strip()
        try:
            Fernet(key)
        except Exception as e:
            raise RuntimeError("MASTER_KEY_INVALID") from e
        return key, False

    # Missing master key file
    existing = _credentials_rowcount()
    if existing > 0 and reset_credentials_if_missing:
        _wipe_credentials()
        _LAST_AUTO_RESET = True
    elif existing > 0 and not reset_credentials_if_missing:
        raise RuntimeError("MASTER_KEY_MISSING_AND_CREDENTIALS_EXIST")

    key = Fernet.generate_key()
    p.write_bytes(key)
    return key, _LAST_AUTO_RESET


def last_auto_reset() -> bool:
    return _LAST_AUTO_RESET


def _fernet() -> Fernet:
    key, _ = ensure_master_key(reset_credentials_if_missing=True)
    return Fernet(key)


def _normalise_supplier(supplier: str) -> str:
    s = (supplier or "").strip().lower()
    if s not in SUPPORTED:
        raise ValueError(f"UNSUPPORTED_SUPPLIER: {s}")
    return s


def set_api_key(supplier: str, api_key: str) -> None:
    supplier = _normalise_supplier(supplier)
    api_key = (api_key or "").strip()
    if len(api_key) < 10:
        raise ValueError("INVALID_API_KEY")

    token = _fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")

    c = connect()
    try:
        c.execute(
            """
            INSERT INTO api_credentials (supplier, token, created_at, updated_at)
            VALUES (?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(supplier) DO UPDATE SET
              token=excluded.token,
              updated_at=datetime('now')
            """,
            (supplier, token),
        )
        c.commit()
    finally:
        c.close()


def delete_api_key(supplier: str) -> None:
    supplier = _normalise_supplier(supplier)
    c = connect()
    try:
        c.execute("DELETE FROM api_credentials WHERE supplier=?", (supplier,))
        c.commit()
    finally:
        c.close()


def has_api_key(supplier: str) -> bool:
    supplier = _normalise_supplier(supplier)
    c = connect()
    try:
        r = c.execute(
            "SELECT 1 FROM api_credentials WHERE supplier=? LIMIT 1", (supplier,)
        ).fetchone()
        return r is not None
    finally:
        c.close()


def get_api_key(supplier: str) -> str:
    supplier = _normalise_supplier(supplier)

    c = connect()
    try:
        row = c.execute(
            "SELECT token FROM api_credentials WHERE supplier=? LIMIT 1", (supplier,)
        ).fetchone()
    finally:
        c.close()

    if not row:
        raise RuntimeError(f"MISSING_CREDENTIALS_{supplier.upper()}")

    token = row["token"]
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise RuntimeError("CREDENTIAL_DECRYPT_FAILED")


def credentials_status() -> Dict[str, bool]:
    ensure_master_key(reset_credentials_if_missing=True)
    return {s: has_api_key(s) for s in SUPPORTED}
