from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

if "new Audio(audioUrl)" in content:
    print("audioUrl playback bridge already repaired.")
else:
    if "new Audio(data.audioUrl)" not in content:
        raise SystemExit("Could not find exact served bridge token: new Audio(data.audioUrl)")

    content = content.replace(
        "if (data.audioUrl) {",
        "const audioUrl = data.audioUrl;\\n  if (audioUrl) {",
        1,
    )
    content = content.replace(
        "new Audio(data.audioUrl)",
        "new Audio(audioUrl)",
        1,
    )

    init_file.write_text(content, encoding="utf-8")
    print("Repaired served runtime bridge from data.audioUrl to audioUrl variable.")

