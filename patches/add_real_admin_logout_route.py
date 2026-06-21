from __future__ import annotations

import re
from pathlib import Path

admin_file = Path("src/smx_visiondirector/admin_dashboard.py")
content = admin_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# 1) Ensure Flask imports include session and redirect.
# ---------------------------------------------------------------------
lines = content.splitlines()

for i, line in enumerate(lines):
    if line.startswith("from flask import "):
        imported = line.replace("from flask import ", "").strip()
        names = [name.strip() for name in imported.split(",") if name.strip()]
        for required in ("redirect", "session"):
            if required not in names:
                names.append(required)
        lines[i] = "from flask import " + ", ".join(sorted(names))
        break
else:
    raise SystemExit("Could not find Flask import line.")

content = "\n".join(lines) + "\n"


# ---------------------------------------------------------------------
# 2) Add a real admin logout route beside the existing login route.
# ---------------------------------------------------------------------
if "/admin/logout" in content or "/visiondirector/admin/logout" in content:
    print("Admin logout route/link already present somewhere; checking if route exists.")

route_pattern = re.compile(
    r'^(?P<indent>\s*)@(?P<receiver>[A-Za-z_][A-Za-z0-9_]*)\.(?P<method>route|get|post)\((?P<args>.*admin/login.*)\)',
    re.MULTILINE,
)

match = route_pattern.search(content)
if not match:
    raise SystemExit("Could not find existing admin login route decorator.")

indent = match.group("indent")
receiver = match.group("receiver")
login_args = match.group("args")

if "/visiondirector/admin/login" in login_args:
    logout_path = "/visiondirector/admin/logout"
    login_redirect = "/visiondirector/admin/login"
else:
    logout_path = "/admin/logout"
    login_redirect = "/visiondirector/admin/login"

route_decorator = f'{indent}@{receiver}.route("{logout_path}", methods=["GET", "POST"])'
route_signature = f"{indent}def _smx_visiondirector_admin_logout():"

if route_signature not in content:
    # Insert before the next route decorator after the login handler block.
    login_decorator_start = match.start()
    next_route_match = re.search(
        rf'\n{re.escape(indent)}@{re.escape(receiver)}\.(route|get|post)\(',
        content[match.end():],
    )

    if next_route_match:
        insert_at = match.end() + next_route_match.start() + 1
    else:
        raise SystemExit("Could not find the next route decorator after admin login.")

    logout_block = (
        f'\n{route_decorator}\n'
        f'{route_signature}\n'
        f'{indent}    """Log out the VisionDirector admin user without touching host app sessions."""\n'
        f'{indent}    for key in list(session.keys()):\n'
        f'{indent}        key_text = str(key).lower()\n'
        f'{indent}        if "admin" in key_text and (\n'
        f'{indent}            "visiondirector" in key_text\n'
        f'{indent}            or "vision_director" in key_text\n'
        f'{indent}            or "smx_vd" in key_text\n'
        f'{indent}            or "smx-visiondirector" in key_text\n'
        f'{indent}        ):\n'
        f'{indent}            session.pop(key, None)\n'
        f'{indent}    return redirect("{login_redirect}")\n'
    )

    content = content[:insert_at] + logout_block + content[insert_at:]
    print("Added real admin logout route.")
else:
    print("Real admin logout route already exists.")


# ---------------------------------------------------------------------
# 3) Make sure visible link points to the real public route.
# ---------------------------------------------------------------------
content = content.replace(
    'href="/admin/logout"',
    'href="/visiondirector/admin/logout"',
)

admin_file.write_text(content, encoding="utf-8")
print("Saved admin_dashboard.py with real logout route.")
