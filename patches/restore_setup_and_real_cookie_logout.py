from __future__ import annotations

import ast
import re
from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# 1) Replace logout body with real cookie deletion.
#    Login uses ADMIN_COOKIE_NAME, so logout must delete that cookie.
# ---------------------------------------------------------------------
old_logout = re.compile(
    r'''
    (?P<decorator>\n[ ]{4}@bp\.route\("/admin/logout",\s*methods=\["GET",\s*"POST"\]\)\n)
    [ ]{4}def\s+_smx_visiondirector_admin_logout\(\):\n
    (?P<body>.*?)
    (?=\n[ ]{4}(?:@bp\.|return\s+bp)|\Z)
    ''',
    re.VERBOSE | re.DOTALL,
)

new_logout = dedent(
    '''
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
)

content, replaced = old_logout.subn("\n" + new_logout, content, count=1)
if replaced != 1:
    raise SystemExit(f"Expected to replace one logout route, replaced {replaced}.")

print("Replaced logout route with real admin-cookie deletion.")


# ---------------------------------------------------------------------
# 2) Re-parse and restore `return bp` at the end of create_visiondirector_blueprint.
# ---------------------------------------------------------------------
tree = ast.parse(content)

create_node = None
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == "create_visiondirector_blueprint":
        create_node = node
        break

if create_node is None:
    raise SystemExit("Could not find create_visiondirector_blueprint.")

lines = content.splitlines(keepends=True)

# Check whether the function already has a final top-level `return bp`.
body_text = "".join(lines[create_node.lineno - 1:create_node.end_lineno])
has_return_bp = "\n    return bp" in body_text

if not has_return_bp:
    lines.insert(create_node.end_lineno, "\n    return bp\n")
    content = "".join(lines)
    print("Restored final `return bp` inside create_visiondirector_blueprint.")
else:
    content = "".join(lines)
    print("Final `return bp` already present.")


# ---------------------------------------------------------------------
# 3) Restore public setup_visiondirector wrapper at module level.
# ---------------------------------------------------------------------
if "def setup_visiondirector(" not in content:
    setup_wrapper = dedent(
        '''

        def setup_visiondirector(app, **kwargs):
            """
            Register VisionDirector on a host Flask app.

            This is the public integration API used by SyntaxMatrix host projects.
            It creates the VisionDirector blueprint, registers it under the plugin
            root path, and returns the registered blueprint.
            """
            url_prefix = str(kwargs.pop("url_prefix", DEFAULT_URL_PREFIX))
            blueprint = create_visiondirector_blueprint(**kwargs)
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            return blueprint
        '''
    ).lstrip()

    content = content.rstrip() + "\n\n" + setup_wrapper
    print("Restored public setup_visiondirector wrapper.")
else:
    print("setup_visiondirector already present.")


# ---------------------------------------------------------------------
# 4) Final syntax and export checks.
# ---------------------------------------------------------------------
tree = ast.parse(content)
top_level_functions = {
    node.name for node in tree.body if isinstance(node, ast.FunctionDef)
}

if "create_visiondirector_blueprint" not in top_level_functions:
    raise SystemExit("create_visiondirector_blueprint missing after repair.")
if "setup_visiondirector" not in top_level_functions:
    raise SystemExit("setup_visiondirector missing after repair.")

init_file.write_text(content, encoding="utf-8")
print("Saved __init__.py repair.")
