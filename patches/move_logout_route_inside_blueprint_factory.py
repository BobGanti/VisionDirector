from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")
lines = content.splitlines(keepends=True)


# ---------------------------------------------------------------------
# 1) Remove broken module-level logout route blocks.
#    Only remove @bp.route("/admin/logout"... with ZERO indentation.
# ---------------------------------------------------------------------
cleaned: list[str] = []
i = 0
removed = 0

while i < len(lines):
    line = lines[i]

    if line.startswith('@bp.route("/admin/logout"') or line.startswith("@bp.route('/admin/logout'"):
        removed += 1
        i += 1

        # Skip the function body until the next top-level definition/import/class
        # or end of file.
        while i < len(lines):
            next_line = lines[i]
            if (
                next_line.startswith("def ")
                or next_line.startswith("class ")
                or next_line.startswith("from ")
                or next_line.startswith("import ")
                or next_line.startswith("__all__")
            ):
                break
            i += 1

        continue

    cleaned.append(line)
    i += 1

content = "".join(cleaned)
print(f"Removed {removed} broken module-level logout route block(s).")


# ---------------------------------------------------------------------
# 2) Ensure redirect is importable.
# ---------------------------------------------------------------------
if "redirect" not in content.split("\n", 40)[0:40].__str__():
    # Safer than editing multiline Flask imports: add a direct import.
    content = content.replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\n\nfrom flask import redirect\n",
        1,
    )
    print("Added redirect import.")
else:
    print("redirect import already available near top of file.")


# ---------------------------------------------------------------------
# 3) Insert logout route inside create_visiondirector_blueprint()
#    before the function-level `return bp`.
# ---------------------------------------------------------------------
if '    @bp.route("/admin/logout", methods=["GET", "POST"])' not in content:
    marker = "\n    return bp\n"
    idx = content.rfind(marker)
    if idx < 0:
        raise SystemExit("Could not find function-level `return bp` marker.")

    logout_block = '''
    @bp.route("/admin/logout", methods=["GET", "POST"])
    def _smx_visiondirector_admin_logout():
        """Log out the VisionDirector admin user by clearing the admin cookie."""
        response = make_response(redirect("/visiondirector/admin/login"))
        response.delete_cookie(
            ADMIN_COOKIE_NAME,
            path=DEFAULT_URL_PREFIX,
        )
        return response

'''

    content = content[:idx + 1] + logout_block + content[idx + 1:]
    print("Inserted logout route inside create_visiondirector_blueprint().")
else:
    print("Blueprint-level logout route already present.")


# ---------------------------------------------------------------------
# 4) Safety checks.
# ---------------------------------------------------------------------
if '@bp.route("/admin/logout"' in content:
    for line in content.splitlines():
        if line.startswith('@bp.route("/admin/logout"') or line.startswith("@bp.route('/admin/logout'"):
            raise SystemExit("A module-level logout route still remains.")

if "def setup_visiondirector(" not in content:
    raise SystemExit("setup_visiondirector is still missing.")

if "\n    return bp\n" not in content:
    raise SystemExit("create_visiondirector_blueprint is missing return bp.")

init_file.write_text(content, encoding="utf-8")
print("Saved __init__.py with logout route inside blueprint factory.")
