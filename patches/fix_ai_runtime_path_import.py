from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"

content = runtime_file.read_text(encoding="utf-8")

if "from pathlib import Path" not in content:
    # Put it with the standard-library imports.
    if "from dataclasses import dataclass\n" in content:
        content = content.replace(
            "from dataclasses import dataclass\n",
            "from dataclasses import dataclass\nfrom pathlib import Path\n",
            1,
        )
    else:
        content = "from pathlib import Path\n" + content
    print("added pathlib.Path import")
else:
    print("pathlib.Path import already present")

runtime_file.write_text(content, encoding="utf-8")
