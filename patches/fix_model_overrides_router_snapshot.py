from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

content = init_file.read_text(encoding="utf-8")

match = re.search(
    r"(?m)^(?P<indent>\s*)model_overrides_store\s*=\s*SQLiteModelOverridesStore\(resolved_storage\)\n",
    content,
)

if not match:
    raise SystemExit("Could not find SQLiteModelOverridesStore assignment.")

if "_model_overrides_snapshot" not in content:
    indent = match.group("indent")
    helper = (
        f"{indent}def _model_overrides_snapshot() -> dict[str, dict[str, str]]:\n"
        f"{indent}    if hasattr(model_overrides_store, \"to_dict\"):\n"
        f"{indent}        return model_overrides_store.to_dict()\n"
        f"{indent}    return model_overrides_store\n\n"
    )
    content = content[: match.end()] + helper + content[match.end():]
    print("added model override snapshot helper")
else:
    print("model override snapshot helper already present")

content = content.replace(
    "overrides_store=model_overrides_store",
    "overrides_store=_model_overrides_snapshot()",
)

init_file.write_text(content, encoding="utf-8")
print("Patched router calls to use plain override snapshots.")
