from __future__ import annotations

import ast
import re
from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# 1) Remove any broken previously injected logout route block.
# ---------------------------------------------------------------------
lines = content.splitlines(keepends=True)
remove_ranges: list[tuple[int, int]] = []

for i, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped.startswith("@") and "admin/logout" in stripped:
        end = i + 1
        while end < len(lines):
            if "return redirect(" in lines[end]:
                end += 1
                break
            end += 1
        remove_ranges.append((i, end))

if remove_ranges:
    for start, end in reversed(remove_ranges):
        del lines[start:end]
    content = "".join(lines)
    print(f"Removed {len(remove_ranges)} broken logout route block(s).")
else:
    print("No broken logout route decorator block found.")


# ---------------------------------------------------------------------
# 2) Ensure redirect/session import exists.
# ---------------------------------------------------------------------
if "from flask import redirect, session" not in content:
    future = "from __future__ import annotations\n"
    if future in content:
        content = content.replace(
            future,
            future + "\nfrom flask import redirect, session\n",
            1,
        )
    else:
        content = "from flask import redirect, session\n" + content
    print("Ensured redirect/session import.")
else:
    print("redirect/session import already present.")


# ---------------------------------------------------------------------
# 3) Parse repaired file and locate the real admin login route.
# ---------------------------------------------------------------------
tree = ast.parse(content)

login_node = None
login_decorator = None

for node in ast.walk(tree):
    if not isinstance(node, ast.FunctionDef):
        continue

    for decorator in node.decorator_list:
        segment = ast.get_source_segment(content, decorator) or ""
        if "admin/login" in segment:
            login_node = node
            login_decorator = segment
            break

    if login_node:
        break

if login_node is None or login_decorator is None:
    raise SystemExit("Could not find admin login route after cleanup.")

decorator_match = re.search(
    r'(?P<receiver>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\.route\(',
    login_decorator,
)

if not decorator_match:
    raise SystemExit(f"Could not parse login route decorator: {login_decorator!r}")

receiver = decorator_match.group("receiver")

path_match = re.search(r'["\'](?P<path>[^"\']*admin/login[^"\']*)["\']', login_decorator)
if not path_match:
    raise SystemExit(f"Could not parse login route path: {login_decorator!r}")

login_route_path = path_match.group("path")
logout_route_path = login_route_path.replace("login", "logout")

indent = " " * login_node.col_offset

logout_block = (
    "\n"
    f'{indent}@{receiver}.route("{logout_route_path}", methods=["GET", "POST"])\n'
    f"{indent}def _smx_visiondirector_admin_logout():\n"
    f'{indent}    """Log out the VisionDirector admin user without clearing host app sessions."""\n'
    f"{indent}    for key in list(session.keys()):\n"
    f"{indent}        key_text = str(key).lower()\n"
    f"{indent}        if \"admin\" in key_text and (\n"
    f"{indent}            \"visiondirector\" in key_text\n"
    f"{indent}            or \"vision_director\" in key_text\n"
    f"{indent}            or \"smx_visiondirector\" in key_text\n"
    f"{indent}            or \"smx_vd\" in key_text\n"
    f"{indent}            or key_text.startswith(\"vd_\")\n"
    f"{indent}        ):\n"
    f"{indent}            session.pop(key, None)\n"
    f'{indent}    return redirect("/visiondirector/admin/login")\n'
)

lines = content.splitlines(keepends=True)
insert_at = login_node.end_lineno
lines.insert(insert_at, logout_block)
content = "".join(lines)

# Final safety: only one logout route decorator.
if content.count("admin/logout") < 1:
    raise SystemExit("Logout route was not inserted.")
if content.count('route("/admin/logout"') > 1:
    raise SystemExit("Duplicate /admin/logout route inserted.")

init_file.write_text(content, encoding="utf-8")
print(f"Inserted real logout route cleanly: {logout_route_path}")
