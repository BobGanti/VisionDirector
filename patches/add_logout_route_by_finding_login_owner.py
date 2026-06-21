from __future__ import annotations

import ast
import re
from pathlib import Path

src_root = Path("src/smx_visiondirector")
candidates = list(src_root.rglob("*.py"))

target_file = None
target_node = None
target_decorator = None
target_source = None

for path in candidates:
    text = path.read_text(encoding="utf-8")
    if "admin/login" not in text and "/login" not in text:
        continue

    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        for decorator in node.decorator_list:
            segment = ast.get_source_segment(text, decorator) or ""
            if "admin/login" in segment:
                target_file = path
                target_node = node
                target_decorator = segment
                target_source = text
                break

        if target_file:
            break

    if target_file:
        break

if not target_file or not target_node or not target_decorator or target_source is None:
    raise SystemExit("Could not find the actual admin login route owner.")

print(f"Found admin login route in: {target_file}")

content = target_source

# Add a separate Flask import. This avoids fragile editing of multiline imports.
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
    print("Added redirect/session import.")
else:
    print("redirect/session import already present.")

# Do not rely on the link text. Only skip if the actual route function exists.
if "def _smx_visiondirector_admin_logout(" not in content:
    match = re.search(
        r'(?P<receiver>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\.(?P<method>route|get|post)\((?P<args>.*)\)',
        target_decorator,
        flags=re.DOTALL,
    )

    if not match:
        raise SystemExit(f"Could not parse login route decorator: {target_decorator!r}")

    receiver = match.group("receiver")
    args = match.group("args")

    string_match = re.search(r'["\'](?P<path>[^"\']*admin/login[^"\']*)["\']', args)
    if not string_match:
        raise SystemExit(f"Could not parse login route path from decorator: {target_decorator!r}")

    login_route_path = string_match.group("path")
    logout_route_path = login_route_path.replace("login", "logout")

    indent = " " * target_node.col_offset

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
    insert_at = target_node.end_lineno
    lines.insert(insert_at, logout_block)
    content = "".join(lines)

    print(f"Added real logout route: {logout_route_path}")
else:
    print("Logout route function already exists.")

# Ensure any visible logout link points to the public namespaced route.
content = content.replace(
    'href="/admin/logout"',
    'href="/visiondirector/admin/logout"',
)

target_file.write_text(content, encoding="utf-8")
print("Saved real admin logout route.")
