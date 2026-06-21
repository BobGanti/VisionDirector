from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

content = init_file.read_text(encoding="utf-8")

pattern = re.compile(
    r"\n\s*model_overrides_store:\s*dict\[str,\s*dict\[str,\s*str\]\]\s*=\s*\{\s*"
    r'"google":\s*\{\},\s*'
    r'"openai":\s*\{\},\s*'
    r"\}",
    re.MULTILINE,
)

replacement = "\n    model_overrides_store = SQLiteModelOverridesStore(resolved_storage)"

content, count = pattern.subn(replacement, content, count=1)

if count != 1:
    raise SystemExit("Could not replace in-memory model_overrides_store block.")

init_file.write_text(content, encoding="utf-8")
print("Replaced in-memory model_overrides_store with SQLiteModelOverridesStore.")
