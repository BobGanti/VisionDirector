# data/db.py
import os
import sqlite3
from typing import Optional

DEFAULT_DB_PATH = os.path.join("data", "syntaxmatrixdir", "db.sqlite")

def get_db_path() -> str:
    """
    Dev default: data/syntaxmatrixdir/db.sqlite
    Prod: set DATABASE_PATH to mounted volume path (e.g. /mnt/visiondirector/db/app.db)
    """
    return os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)

def ensure_db_dir_exists(db_path: Optional[str] = None) -> None:
    p = db_path or get_db_path()
    d = os.path.dirname(p)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def connect() -> sqlite3.Connection:
    ensure_db_dir_exists()
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn
