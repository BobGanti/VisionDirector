# data/cred_master_key.py
import base64
import os
from pathlib import Path

from .db import get_db_path

DEFAULT_KEY_FILE = str(Path(get_db_path()).resolve().parent / ".vd_master_key")

def load_master_key() -> bytes:
    """
    Loads a 32-byte master key for AES-256-GCM.

    Precedence:
      1) env: VD_CRED_MASTER_KEY_B64
      2) file: VD_CRED_MASTER_KEY_FILE (default: data/syntaxmatrixdir/.vd_master_key)
    """
    b64 = (os.environ.get("VD_CRED_MASTER_KEY_B64") or "").strip()
    if not b64:
        key_file = (os.environ.get("VD_CRED_MASTER_KEY_FILE") or DEFAULT_KEY_FILE).strip()
        p = Path(key_file)
        if not p.exists():
            raise RuntimeError(f"MASTER_KEY_MISSING: set VD_CRED_MASTER_KEY_B64 or create {key_file}")
        b64 = p.read_text(encoding="utf-8").strip()

    try:
        key = base64.b64decode(b64, validate=True)
    except Exception as e:
        raise RuntimeError("MASTER_KEY_INVALID_BASE64") from e

    if len(key) != 32:
        raise RuntimeError(f"MASTER_KEY_INVALID_LEN: expected 32 bytes, got {len(key)}")

    return key
