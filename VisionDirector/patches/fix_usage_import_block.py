from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

lines = init_file.read_text(encoding="utf-8").splitlines()

start = None
for i, line in enumerate(lines):
    if line.startswith("from .usage import"):
        start = i
        break

if start is None:
    raise SystemExit("Could not find .usage import line.")

end = start + 1
while end < len(lines):
    line = lines[end]
    stripped = line.strip()

    # Remove continuation lines created by the broken import.
    if not stripped:
        break
    if line.startswith(" ") or line.startswith("    "):
        end += 1
        continue
    if stripped in {
        "SQLiteUsageRecorder,",
        "InMemoryUsageRecorder,",
        "JsonlUsageRecorder,",
        "UsageRecorder,",
    }:
        end += 1
        continue
    break

replacement = [
    "from .usage import (",
    "    InMemoryUsageRecorder,",
    "    JsonlUsageRecorder,",
    "    SQLiteUsageRecorder,",
    "    UsageRecorder,",
    ")",
]

lines[start:end] = replacement

init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Fixed .usage import block.")
