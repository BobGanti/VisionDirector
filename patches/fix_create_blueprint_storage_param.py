from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not init_file.exists():
    raise SystemExit("Run from VisionDirector root. Missing src/smx_visiondirector/__init__.py.")

content = init_file.read_text(encoding="utf-8")

create_start = content.index("def create_visiondirector_blueprint(")
setup_start = content.index("def setup_visiondirector(", create_start)
create_section = content[create_start:setup_start]

# 1) Make create_visiondirector_blueprint accept storage.
if "storage: VisionDirectorStorage | None = None" not in create_section:
    marker = "    usage_recorder: UsageRecorder | None = None,\n"
    if marker not in create_section:
        raise SystemExit("Could not find usage_recorder parameter in create_visiondirector_blueprint.")

    create_section = create_section.replace(
        marker,
        marker + "    storage: VisionDirectorStorage | None = None,\n",
        1,
    )
    print("added storage parameter to create_visiondirector_blueprint")
else:
    print("create_visiondirector_blueprint already accepts storage")

# 2) Ensure resolved_storage exists inside create_visiondirector_blueprint.
if "resolved_storage = storage" not in create_section:
    lines = create_section.splitlines(keepends=True)

    candidate_indexes = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("resolved_config") and "=" in stripped:
            candidate_indexes.append(idx)
        if stripped.startswith("resolved_project_root") and "=" in stripped:
            candidate_indexes.append(idx)

    if not candidate_indexes:
        raise SystemExit("Could not find resolved_config/resolved_project_root setup lines.")

    insert_after = max(candidate_indexes)
    indent = lines[insert_after][: len(lines[insert_after]) - len(lines[insert_after].lstrip())]

    insert_lines = [
        f"{indent}resolved_storage = storage\n",
        f"{indent}if resolved_storage is None:\n",
        f"{indent}    resolved_storage = build_storage_from_database_url(\n",
        f'{indent}        str(resolved_config.get("SMX_VISIONDIRECTOR_DATABASE_URL") or ""),\n',
        f"{indent}        fallback_sqlite_path=resolved_project_root\n",
        f'{indent}        / "plugins"\n',
        f'{indent}        / "visiondirector"\n',
        f'{indent}        / "data"\n',
        f'{indent}        / "smx_visiondirector_dev.db",\n',
        f"{indent}    )\n",
        f"{indent}    resolved_storage.initialize()\n",
    ]

    lines[insert_after + 1:insert_after + 1] = insert_lines
    create_section = "".join(lines)
    print("added resolved_storage inside create_visiondirector_blueprint")
else:
    print("resolved_storage already present")

# 3) Ensure the model override store uses SQLite storage, not a plain memory dict.
create_section = create_section.replace(
    'model_overrides_store = {"google": {}, "openai": {}}',
    "model_overrides_store = SQLiteModelOverridesStore(resolved_storage)",
)

content = content[:create_start] + create_section + content[setup_start:]
init_file.write_text(content, encoding="utf-8")

print("Patch complete: create_visiondirector_blueprint now accepts and uses storage.")
