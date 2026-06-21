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


content = init_file.read_text(encoding="utf-8")

# 1) Upgrade the storage import safely.
content = re.sub(
    r"from \.storage import [^\n]*build_storage_from_database_url[^\n]*",
    "from .storage import SQLiteModelOverridesStore, VisionDirectorStorage, build_storage_from_database_url",
    content,
    count=1,
)

if "SQLiteModelOverridesStore" not in content:
    marker = "from .model_router import build_model_router\n"
    if marker not in content:
        raise SystemExit("Could not find model_router import marker.")
    content = content.replace(
        marker,
        marker + "from .storage import SQLiteModelOverridesStore, VisionDirectorStorage, build_storage_from_database_url\n",
        1,
    )

# 2) Add optional storage parameter to create_visiondirector_blueprint.
content = re.sub(
    r"(def create_visiondirector_blueprint\([\s\S]*?usage_recorder: UsageRecorder \| None = None,\n)(\s*\):)",
    r"\1    storage: VisionDirectorStorage | None = None,\n\2",
    content,
    count=1,
)

# 3) Add optional storage parameter to init_visiondirector.
content = re.sub(
    r"(def init_visiondirector\([\s\S]*?usage_recorder: UsageRecorder \| None = None,\n)(\s*\):)",
    r"\1    storage: VisionDirectorStorage | None = None,\n\2",
    content,
    count=1,
)

# 4) Create resolved_storage inside blueprint after resolved_project_root exists.
if "resolved_storage = storage" not in content:
    match = re.search(
        r"(?P<line>\s*resolved_project_root\s*=\s*Path\([^\n]+\)\n)",
        content,
    )
    if not match:
        raise SystemExit("Could not find resolved_project_root assignment.")

    indent = re.match(r"\s*", match.group("line")).group(0)
    insert = (
        match.group("line")
        + f"{indent}resolved_storage = storage\n"
        + f"{indent}if resolved_storage is None:\n"
        + f"{indent}    resolved_storage = build_storage_from_database_url(\n"
        + f'{indent}        str(resolved_config.get("SMX_VISIONDIRECTOR_DATABASE_URL") or ""),\n'
        + f"{indent}        fallback_sqlite_path=resolved_project_root\n"
        + f'{indent}        / "plugins"\n'
        + f'{indent}        / "visiondirector"\n'
        + f'{indent}        / "data"\n'
        + f'{indent}        / "smx_visiondirector_dev.db",\n'
        + f"{indent}    )\n"
        + f"{indent}    resolved_storage.initialize()\n"
    )
    content = content[: match.start()] + insert + content[match.end() :]
    print("inserted resolved_storage")
else:
    print("resolved_storage already present")

# 5) Swap the in-memory overrides dict to the SQLite-backed mapping.
content = content.replace(
    'model_overrides_store = {"google": {}, "openai": {}}',
    "model_overrides_store = SQLiteModelOverridesStore(resolved_storage)",
)

# 6) Pass storage through init_visiondirector -> create_visiondirector_blueprint.
content = content.replace(
    "            usage_recorder=usage_recorder,\n        ),",
    "            usage_recorder=usage_recorder,\n            storage=storage,\n        ),",
    1,
)

# 7) Pass storage through setup_visiondirector -> init_visiondirector.
content = content.replace(
    "        usage_recorder=usage_recorder,\n    )",
    "        usage_recorder=usage_recorder,\n        storage=storage,\n    )",
    1,
)

init_file.write_text(content, encoding="utf-8")

write_file(
    "tests/test_sqlite_model_overrides.py",
    """
    from __future__ import annotations

    import sqlite3

    from flask import Flask

    from smx_visiondirector import init_visiondirector, setup_visiondirector
    from smx_visiondirector.storage import SQLiteModelOverridesStore, build_sqlite_storage


    def test_sqlite_model_override_store_persists_across_instances(tmp_path):
        db_path = (
            tmp_path
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db"
        )
        storage = build_sqlite_storage(db_path)
        storage.initialize()

        store = SQLiteModelOverridesStore(storage)
        store["google"]["VIDEO_GEN"] = "veo-db-test-model"

        fresh_store = SQLiteModelOverridesStore(build_sqlite_storage(db_path))

        assert fresh_store["google"]["VIDEO_GEN"] == "veo-db-test-model"
        assert fresh_store["google"].get("VIDEO_GEN") == "veo-db-test-model"
        assert dict(fresh_store["google"].items())["VIDEO_GEN"] == "veo-db-test-model"


    def test_model_map_uses_sqlite_backed_overrides(tmp_path):
        db_path = (
            tmp_path
            / "plugins"
            / "visiondirector"
            / "data"
            / "smx_visiondirector_dev.db"
        )
        storage = build_sqlite_storage(db_path)
        storage.initialize()

        store = SQLiteModelOverridesStore(storage)
        store["google"]["VIDEO_GEN"] = "veo-from-sqlite"

        app = Flask(__name__)
        init_visiondirector(app, project_root=tmp_path, storage=storage)

        response = app.test_client().get("/visiondirector/api/model-map/google")

        assert response.status_code == 200
        assert "veo-from-sqlite" in response.get_data(as_text=True)


    def test_setup_visiondirector_model_override_table_is_real_sqlite_table(tmp_path):
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
                "WHERE type='table' AND name='visiondirector_model_overrides'"
            ).fetchone()

        assert row is not None
    """,
)

print("Patch complete: __init__.py is wired for SQLite model overrides.")
