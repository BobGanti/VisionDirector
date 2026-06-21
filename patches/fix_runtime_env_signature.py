from __future__ import annotations

from pathlib import Path
import re

smxcp_file = Path("src/smx_visiondirector/smxcp.py")
content = smxcp_file.read_text(encoding="utf-8")

old = "def _render_runtime_env_file() -> str:"
new = "def _render_runtime_env_file(*, assets_dir: Path | None = None) -> str:"

if old not in content:
    if new in content:
        print("_render_runtime_env_file signature already accepts assets_dir.")
    else:
        raise SystemExit("Could not find _render_runtime_env_file signature.")
else:
    content = content.replace(old, new, 1)
    smxcp_file.write_text(content, encoding="utf-8")
    print("Updated _render_runtime_env_file signature to accept assets_dir.")
