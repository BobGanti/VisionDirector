from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"

content = runtime_file.read_text(encoding="utf-8")

old = "    operation = generate(**kwargs)\n"
new = '''    try:
        operation = generate(**kwargs)
    except Exception as exc:
        raise VisionDirectorAIExecutionError(str(exc)) from exc
'''

if old not in content:
    raise SystemExit("Could not find Google video generate operation call.")

content = content.replace(old, new, 1)

runtime_file.write_text(content, encoding="utf-8")
print("Wrapped Google video provider exceptions as VisionDirectorAIExecutionError.")
