from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

lines = init_file.read_text(encoding="utf-8").splitlines()

start = None
for i, line in enumerate(lines):
    if line == '@bp.get("/api/render-jobs")':
        start = i
        break

if start is None:
    print("No top-level render job route block found; nothing to indent.")
else:
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j] == '    @bp.post("/api/ai/generate-video")':
            end = j
            break

    if end is None:
        raise SystemExit("Could not find generate-video route marker after render-job route block.")

    for k in range(start, end):
        if lines[k].strip():
            lines[k] = "    " + lines[k]

    init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Indented render-job route block lines {start + 1} through {end} into create_visiondirector_blueprint.")
