from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not init_file.exists():
    raise SystemExit("Run from VisionDirector root. Missing src/smx_visiondirector/__init__.py.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


write_file(
    "src/smx_visiondirector/storage.py",
    """
    from __future__ import annotations

    import json
    import sqlite3
    from dataclasses import dataclass
    from pathlib import Path
    from typing import Any


    SCHEMA_VERSION = 1


    @dataclass(frozen=True)
    class VisionDirectorStorageConfig:
        database_url: str
        sqlite_path: Path | None
        backend: str


    class VisionDirectorStorage:
        \"\"\"VisionDirector plugin-owned storage.

        Local development uses SQLite under the host plugin folder:
            plugins/visiondirector/data/smx_visiondirector_dev.db

        Production should be wired to a host-managed PostgreSQL database URL
        in a later patch. Provider secrets remain host-owned and are not stored
        here.
        \"\"\"

        def __init__(self, config: VisionDirectorStorageConfig):
            self.config = config

        @property
        def backend(self) -> str:
            return self.config.backend

        @property
        def sqlite_path(self) -> Path | None:
            return self.config.sqlite_path

        def initialize(self) -> None:
            if self.config.backend != "sqlite":
                raise NotImplementedError(
                    "VisionDirector PostgreSQL storage contract exists, but the "
                    "PostgreSQL adapter has not been wired in this patch."
                )

            if self.config.sqlite_path is None:
                raise ValueError("sqlite_path is required for SQLite storage")

            self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.config.sqlite_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                _create_schema(conn)
                conn.commit()

        def table_names(self) -> set[str]:
            if self.config.backend != "sqlite" or self.config.sqlite_path is None:
                return set()

            if not self.config.sqlite_path.exists():
                return set()

            with sqlite3.connect(self.config.sqlite_path) as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            return {str(row[0]) for row in rows}

        def schema_version(self) -> int:
            if self.config.backend != "sqlite" or self.config.sqlite_path is None:
                return 0

            if not self.config.sqlite_path.exists():
                return 0

            with sqlite3.connect(self.config.sqlite_path) as conn:
                row = conn.execute(
                    "SELECT version FROM visiondirector_schema_migrations "
                    "ORDER BY version DESC LIMIT 1"
                ).fetchone()
            return int(row[0]) if row else 0

        def storage_status(self) -> dict[str, Any]:
            return {
                "backend": self.config.backend,
                "databaseUrl": self.config.database_url,
                "sqlitePath": str(self.config.sqlite_path) if self.config.sqlite_path else None,
                "schemaVersion": self.schema_version(),
                "tables": sorted(self.table_names()),
            }


    def build_sqlite_storage(sqlite_path: Path) -> VisionDirectorStorage:
        return VisionDirectorStorage(
            VisionDirectorStorageConfig(
                database_url=f"sqlite:///{sqlite_path.as_posix()}",
                sqlite_path=sqlite_path,
                backend="sqlite",
            )
        )


    def build_storage_from_database_url(
        database_url: str,
        *,
        fallback_sqlite_path: Path,
    ) -> VisionDirectorStorage:
        clean = str(database_url or "").strip()

        if not clean:
            return build_sqlite_storage(fallback_sqlite_path)

        if clean.startswith("sqlite:///"):
            return build_sqlite_storage(Path(clean.removeprefix("sqlite:///")))

        if clean.startswith(("postgresql://", "postgres://")):
            return VisionDirectorStorage(
                VisionDirectorStorageConfig(
                    database_url=clean,
                    sqlite_path=None,
                    backend="postgresql",
                )
            )

        raise ValueError(f"Unsupported VisionDirector database URL: {clean}")


    def _create_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(
            \"\"\"
            CREATE TABLE IF NOT EXISTS visiondirector_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS visiondirector_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS visiondirector_model_overrides (
                supplier TEXT NOT NULL,
                task TEXT NOT NULL,
                model TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (supplier, task)
            );

            CREATE TABLE IF NOT EXISTS visiondirector_voice_identities (
                id TEXT PRIMARY KEY,
                supplier TEXT NOT NULL,
                label TEXT NOT NULL,
                base_voice TEXT NOT NULL,
                traits TEXT NOT NULL,
                speed TEXT NOT NULL DEFAULT 'natural',
                sentiment TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS visiondirector_usage_events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                operation TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT,
                role TEXT,
                status TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                cached_tokens INTEGER NOT NULL DEFAULT 0,
                reasoning_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS visiondirector_render_jobs (
                id TEXT PRIMARY KEY,
                supplier TEXT NOT NULL,
                status TEXT NOT NULL,
                prompt TEXT,
                model TEXT,
                video_url TEXT,
                video_ref_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS visiondirector_assets (
                id TEXT PRIMARY KEY,
                asset_type TEXT NOT NULL,
                url TEXT,
                file_name TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            INSERT OR IGNORE INTO visiondirector_schema_migrations(version)
            VALUES (1);
            \"\"\"
        )


    def dumps_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)


    def loads_json(value: str | None) -> Any:
        if not value:
            return {}
        return json.loads(value)
    """,
)

content = init_file.read_text(encoding="utf-8")

if "from .storage import build_storage_from_database_url, build_sqlite_storage" not in content:
    inserted = False

    usage_block = re.search(r"from \.usage import \([\s\S]*?\)\n", content)
    if usage_block:
        pos = usage_block.end()
        content = (
            content[:pos]
            + "from .storage import build_storage_from_database_url, build_sqlite_storage\n"
            + content[pos:]
        )
        inserted = True
    elif "from .usage import " in content:
        content = content.replace(
            "\nfrom .usage import ",
            "\nfrom .storage import build_storage_from_database_url, build_sqlite_storage\nfrom .usage import ",
            1,
        )
        inserted = True

    if not inserted:
        raise SystemExit("Could not find usage import block to insert storage import.")

if "smx_visiondirector_dev.db" not in content:
    pattern = re.compile(
        r"(?P<indent>\s*)resolved_usage_recorder\s*=\s*JsonlUsageRecorder\(scaffold\.data_dir / \"usage_events\.jsonl\"\)",
    )
    match = pattern.search(content)
    if not match:
        raise SystemExit("Could not find resolved_usage_recorder initialization.")

    indent = match.group("indent")
    replacement = (
        f'{indent}storage = build_storage_from_database_url(\n'
        f'{indent}    "",\n'
        f'{indent}    fallback_sqlite_path=scaffold.data_dir / "smx_visiondirector_dev.db",\n'
        f'{indent})\n'
        f'{indent}storage.initialize()\n'
        f'{match.group(0)}'
    )
    content = content[: match.start()] + replacement + content[match.end() :]
    print("wired setup_visiondirector to initialize local dev SQLite DB")
else:
    print("local dev SQLite DB initialization already present")

init_file.write_text(content, encoding="utf-8")

write_file(
    "tests/test_storage_foundation.py",
    """
    from __future__ import annotations

    import sqlite3

    from flask import Flask

    from smx_visiondirector import setup_visiondirector
    from smx_visiondirector.storage import build_sqlite_storage


    REQUIRED_TABLES = {
        "visiondirector_schema_migrations",
        "visiondirector_settings",
        "visiondirector_model_overrides",
        "visiondirector_voice_identities",
        "visiondirector_usage_events",
        "visiondirector_render_jobs",
        "visiondirector_assets",
    }


    def test_sqlite_storage_initializes_core_plugin_tables(tmp_path):
        db_path = tmp_path / "plugins" / "visiondirector" / "data" / "smx_visiondirector_dev.db"

        storage = build_sqlite_storage(db_path)
        storage.initialize()

        assert db_path.exists()
        assert storage.schema_version() == 1
        assert REQUIRED_TABLES.issubset(storage.table_names())


    def test_setup_visiondirector_injects_local_dev_db_into_host_plugin_folder(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(app, project_root=tmp_path)

        db_path = tmp_path / "plugins" / "visiondirector" / "data" / "smx_visiondirector_dev.db"
        assert db_path.exists()

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

        tables = {row[0] for row in rows}
        assert REQUIRED_TABLES.issubset(tables)


    def test_storage_status_does_not_include_provider_secrets(tmp_path):
        db_path = tmp_path / "plugins" / "visiondirector" / "data" / "smx_visiondirector_dev.db"
        storage = build_sqlite_storage(db_path)
        storage.initialize()

        status = storage.storage_status()
        body = str(status).lower()

        assert status["backend"] == "sqlite"
        assert status["schemaVersion"] == 1
        assert "api_key" not in body
        assert "secret" not in body
        assert "password" not in body
    """,
)

print("Patch complete: VisionDirector SQLite storage foundation is installed.")
