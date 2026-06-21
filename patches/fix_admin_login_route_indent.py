from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")
lines = content.splitlines()

start = None
for i, line in enumerate(lines):
    if line.strip() == '@bp.route("/admin/login", methods=["GET", "POST"])':
        start = i
        break

if start is None:
    raise SystemExit("Could not find admin login route block.")

if lines[start].startswith("    "):
    print("Admin login/logout route block is already indented inside the blueprint factory.")
else:
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("    @bp.get(\"/admin\")"):
            end = j
            break

    if end is None:
        raise SystemExit("Could not find following admin dashboard route anchor.")

    fixed = []
    for line in lines[start:end]:
        if line.strip():
            fixed.append("    " + line)
        else:
            fixed.append(line)

    lines = lines[:start] + fixed + lines[end:]
    init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Indented admin login/logout route block lines {start + 1} through {end}.")
