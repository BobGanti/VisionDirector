from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
smxcp_file = ROOT / "src" / "smx_visiondirector" / "smxcp.py"
admin_test_file = ROOT / "tests" / "test_admin_dashboard.py"
smxcp_test_file = ROOT / "tests" / "test_smxcp_contract.py"


# ---------------------------------------------------------------------
# Patch __init__.py admin auth
# ---------------------------------------------------------------------
content = init_file.read_text(encoding="utf-8")

if "import hmac" not in content:
    content = content.replace("import json\n", "import hmac\nimport json\n", 1)

if "from html import escape" not in content:
    content = content.replace("from pathlib import Path\n", "from html import escape\nfrom pathlib import Path\n", 1)

old_import = "from flask import Blueprint, Response, request, send_from_directory, url_for"
new_import = "from flask import Blueprint, Response, make_response, redirect, request, send_from_directory, url_for"
if old_import in content:
    content = content.replace(old_import, new_import, 1)

if "ADMIN_COOKIE_NAME = \"smx_visiondirector_admin_token\"" not in content:
    content = content.replace(
        "DEFAULT_URL_PREFIX = \"/visiondirector\"\n",
        "DEFAULT_URL_PREFIX = \"/visiondirector\"\n"
        "ADMIN_COOKIE_NAME = \"smx_visiondirector_admin_token\"\n",
        1,
    )

if "def _admin_token() -> str:" not in content:
    anchor = "    @bp.get(\"/health\")\n"
    idx = content.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find health route anchor.")

    helpers = dedent(
        '''
            def _admin_token() -> str:
                return str(
                    resolved_config.get("admin_token")
                    or os.environ.get("SMX_VISIONDIRECTOR_ADMIN_TOKEN")
                    or ""
                ).strip()


            def _safe_admin_next_url(value: str | None) -> str:
                candidate = str(value or "").strip()
                if candidate.startswith("/visiondirector/admin"):
                    return candidate
                if candidate.startswith("/admin"):
                    return candidate
                return url_for(".admin_dashboard")


            def _is_admin_authorized() -> bool:
                token = _admin_token()
                if not token:
                    return False

                candidates = [
                    request.cookies.get(ADMIN_COOKIE_NAME, ""),
                    request.headers.get("X-SMX-VISIONDIRECTOR-ADMIN-TOKEN", ""),
                    request.args.get("admin_token", ""),
                    request.args.get("token", ""),
                ]

                return any(
                    hmac.compare_digest(str(candidate), token)
                    for candidate in candidates
                    if candidate
                )


            def _render_admin_login_page(*, error: str = "", next_url: str = "") -> str:
                safe_error = escape(error)
                safe_next = escape(next_url or url_for(".admin_dashboard"))

                error_html = (
                    f'<p class="smx-vd-login-error">{safe_error}</p>'
                    if safe_error
                    else ""
                )

                return f"""<!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>VisionDirector Admin Login</title>
          <style>
            body {{
              margin: 0;
              min-height: 100vh;
              display: grid;
              place-items: center;
              font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              background: #07111f;
              color: #eef4ff;
            }}
            .smx-vd-login-card {{
              width: min(420px, calc(100vw - 32px));
              padding: 28px;
              border: 1px solid rgba(148, 163, 184, 0.35);
              border-radius: 20px;
              background: linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.92));
              box-shadow: 0 24px 80px rgba(0, 0, 0, 0.38);
            }}
            h1 {{ margin: 0 0 8px; font-size: 1.35rem; }}
            p {{ color: #b8c7dd; line-height: 1.5; }}
            label {{ display: block; margin: 18px 0 8px; font-weight: 700; }}
            input {{
              box-sizing: border-box;
              width: 100%;
              padding: 12px 14px;
              border-radius: 12px;
              border: 1px solid rgba(148, 163, 184, 0.55);
              background: rgba(15, 23, 42, 0.8);
              color: #fff;
            }}
            button {{
              width: 100%;
              margin-top: 16px;
              padding: 12px 14px;
              border: 0;
              border-radius: 12px;
              background: #60a5fa;
              color: #07111f;
              font-weight: 800;
              cursor: pointer;
            }}
            .smx-vd-login-error {{
              color: #fecaca;
              background: rgba(127, 29, 29, 0.35);
              border: 1px solid rgba(248, 113, 113, 0.35);
              border-radius: 12px;
              padding: 10px 12px;
            }}
          </style>
        </head>
        <body>
          <main class="smx-vd-login-card">
            <h1>VisionDirector Admin</h1>
            <p>Enter the local or deployed admin token to continue.</p>
            {error_html}
            <form method="post" action="{url_for(".admin_login")}">
              <input type="hidden" name="next" value="{safe_next}">
              <label for="token">Admin token</label>
              <input id="token" name="token" type="password" autocomplete="current-password" required autofocus>
              <button type="submit">Login</button>
            </form>
          </main>
        </body>
        </html>"""


            def _require_admin_response():
                token = _admin_token()
                if not token:
                    return Response(
                        "VisionDirector admin is disabled because SMX_VISIONDIRECTOR_ADMIN_TOKEN is not configured.",
                        status=503,
                        mimetype="text/plain",
                    )

                if _is_admin_authorized():
                    return None

                return redirect(
                    url_for(
                        ".admin_login",
                        next=request.path,
                    )
                )


        '''
    )

    content = content[:idx] + helpers + content[idx:]
    print("added admin auth helpers")
else:
    print("admin auth helpers already present")


if '@bp.route("/admin/login", methods=["GET", "POST"])' not in content:
    anchor = "    @bp.get(\"/admin\")\n"
    idx = content.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find admin dashboard route anchor.")

    routes = dedent(
        '''
            @bp.route("/admin/login", methods=["GET", "POST"])
            def admin_login():
                token = _admin_token()
                next_url = _safe_admin_next_url(request.values.get("next"))

                if not token:
                    return Response(
                        "VisionDirector admin login is unavailable because SMX_VISIONDIRECTOR_ADMIN_TOKEN is not configured.",
                        status=503,
                        mimetype="text/plain",
                    )

                if request.method == "POST":
                    submitted = str(request.form.get("token") or "").strip()
                    if hmac.compare_digest(submitted, token):
                        response = make_response(redirect(next_url))
                        response.set_cookie(
                            ADMIN_COOKIE_NAME,
                            token,
                            httponly=True,
                            secure=request.is_secure,
                            samesite="Lax",
                            path=DEFAULT_URL_PREFIX,
                            max_age=60 * 60 * 12,
                        )
                        return response

                    return Response(
                        _render_admin_login_page(
                            error="Invalid admin token.",
                            next_url=next_url,
                        ),
                        status=401,
                        mimetype="text/html",
                    )

                return Response(
                    _render_admin_login_page(next_url=next_url),
                    mimetype="text/html",
                )


            @bp.post("/admin/logout")
            def admin_logout():
                response = make_response(redirect(url_for(".admin_login")))
                response.delete_cookie(ADMIN_COOKIE_NAME, path=DEFAULT_URL_PREFIX)
                return response


        '''
    )

    content = content[:idx] + routes + content[idx:]
    print("added admin login/logout routes")
else:
    print("admin login/logout routes already present")


old_admin_body = '''    def admin_dashboard():
        return Response(
'''
new_admin_body = '''    def admin_dashboard():
        auth_response = _require_admin_response()
        if auth_response is not None:
            return auth_response

        return Response(
'''

if old_admin_body in content:
    content = content.replace(old_admin_body, new_admin_body, 1)
    print("protected admin dashboard route")
elif "auth_response = _require_admin_response()" in content:
    print("admin dashboard route already protected")
else:
    raise SystemExit("Could not patch admin_dashboard body.")

old_config_tail = '''        "favicon_url": values.get(
            "SMX_VISIONDIRECTOR_FAVICON_URL",
            "/visiondirector/assets/favicon.png",
        ),
    }
'''
new_config_tail = '''        "favicon_url": values.get(
            "SMX_VISIONDIRECTOR_FAVICON_URL",
            "/visiondirector/assets/favicon.png",
        ),
        "admin_token": values.get(
            "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
            os.environ.get("SMX_VISIONDIRECTOR_ADMIN_TOKEN", ""),
        ),
    }
'''
if old_config_tail in content:
    content = content.replace(old_config_tail, new_config_tail, 1)
    print("added admin_token to config loader")
elif '"admin_token": values.get(' in content:
    print("admin_token already present in config loader")
else:
    raise SystemExit("Could not patch config loader admin_token.")

init_file.write_text(content, encoding="utf-8")
print("patched __init__.py admin token login")


# ---------------------------------------------------------------------
# Patch smxcp.py env/scaffold admin token
# ---------------------------------------------------------------------
smxcp = smxcp_file.read_text(encoding="utf-8")

if "def _append_env_line_if_missing(" not in smxcp:
    anchor = '''def _write_bytes_if_missing(path: Path, content: bytes) -> None:
    if not path.exists():
        path.write_bytes(content)
'''
    helper = dedent(
        '''


        def _append_env_line_if_missing(path: Path, key: str, line: str) -> None:
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            if f"{key}=" in existing:
                return

            separator = "" if not existing or existing.endswith("\\n") else "\\n"
            path.write_text(
                existing + separator + line.rstrip() + "\\n",
                encoding="utf-8",
            )
        '''
    )

    if anchor not in smxcp:
        raise SystemExit("Could not find _write_bytes_if_missing helper anchor.")
    smxcp = smxcp.replace(anchor, anchor + helper, 1)
    print("added append env helper")
else:
    print("append env helper already present")


if "_append_env_line_if_missing(env_file, \"SMX_VISIONDIRECTOR_ADMIN_TOKEN\"" not in smxcp:
    anchor = '''    _write_if_missing(deploy_env_example_file, _render_deploy_env_example_file())
'''
    insert = '''    _write_if_missing(deploy_env_example_file, _render_deploy_env_example_file())
    _append_env_line_if_missing(
        env_example_file,
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=replace-with-local-admin-token",
    )
    _append_env_line_if_missing(
        env_file,
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=local-visiondirector-admin-token",
    )
    _append_env_line_if_missing(
        deploy_env_example_file,
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=visiondirector-admin-token-secret-vault:latest",
    )
'''
    if anchor not in smxcp:
        raise SystemExit("Could not find deploy env write anchor.")
    smxcp = smxcp.replace(anchor, insert, 1)
    print("added admin token append calls")
else:
    print("admin token append calls already present")


def replace_in_func(text: str, func_name: str, needle: str, replacement: str) -> str:
    start = text.find(f"def {func_name}")
    if start < 0:
        raise SystemExit(f"Could not find {func_name}.")
    end = text.find("\ndef ", start + 1)
    if end < 0:
        end = len(text)
    segment = text[start:end]
    if "SMX_VISIONDIRECTOR_ADMIN_TOKEN" in segment:
        return text
    if needle not in segment:
        raise SystemExit(f"Could not find admin env insertion point in {func_name}.")
    segment = segment.replace(needle, replacement, 1)
    return text[:start] + segment + text[end:]


smxcp = replace_in_func(
    smxcp,
    "_render_env_example_file",
    '"SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\\n"',
    '"SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\\n\\n"\\n'
    '        "# Local admin access\\n"\\n'
    '        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=replace-with-local-admin-token\\n"',
)

smxcp = replace_in_func(
    smxcp,
    "_render_runtime_env_file",
    '"SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\\n"',
    '"SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\\n\\n"\\n'
    '        "# Local admin access\\n"\\n'
    '        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=local-visiondirector-admin-token\\n"',
)

smxcp = replace_in_func(
    smxcp,
    "_render_deploy_env_example_file",
    '"SMX_VISIONDIRECTOR_DATABASE_URL=visiondirector-database-url-secret-vault:latest\\n',
    '"SMX_VISIONDIRECTOR_DATABASE_URL=visiondirector-database-url-secret-vault:latest\\n"\\n'
    '            "SMX_VISIONDIRECTOR_ADMIN_TOKEN=visiondirector-admin-token-secret-vault:latest\\n',
)

smxcp_file.write_text(smxcp, encoding="utf-8")
print("patched smxcp env examples/admin token append")


# ---------------------------------------------------------------------
# Patch admin dashboard tests to authenticate
# ---------------------------------------------------------------------
admin_tests = admin_test_file.read_text(encoding="utf-8")

if "ADMIN_TOKEN = \"local-visiondirector-admin-token\"" not in admin_tests:
    admin_tests = admin_tests.replace(
        "from smx_visiondirector import setup_visiondirector\n",
        "from smx_visiondirector import setup_visiondirector\n\n\n"
        "ADMIN_TOKEN = \"local-visiondirector-admin-token\"\n\n\n"
        "def _authorized_admin_get(client):\n"
        "    login = client.post(\n"
        "        \"/visiondirector/admin/login\",\n"
        "        data={\"token\": ADMIN_TOKEN, \"next\": \"/visiondirector/admin\"},\n"
        "    )\n"
        "    assert login.status_code in {302, 303}\n"
        "    return client.get(\"/visiondirector/admin\")\n",
        1,
    )

admin_tests = admin_tests.replace(
    "response = client.get(\"/visiondirector/admin\")",
    "response = _authorized_admin_get(client)",
)
admin_tests = admin_tests.replace(
    "    response = app.test_client().get(\"/visiondirector/admin\")\n",
    "    client = app.test_client()\n    response = _authorized_admin_get(client)\n",
)

if "def test_admin_dashboard_requires_admin_token_login" not in admin_tests:
    admin_tests += dedent(
        '''


        def test_admin_dashboard_requires_admin_token_login(tmp_path):
            app = Flask(__name__)
            setup_visiondirector(app, project_root=tmp_path)

            response = app.test_client().get("/visiondirector/admin")

            assert response.status_code in {302, 303}
            assert "/visiondirector/admin/login" in response.headers["Location"]


        def test_admin_login_rejects_wrong_token(tmp_path):
            app = Flask(__name__)
            setup_visiondirector(app, project_root=tmp_path)

            response = app.test_client().post(
                "/visiondirector/admin/login",
                data={"token": "wrong-token", "next": "/visiondirector/admin"},
            )

            assert response.status_code == 401
            assert "Invalid admin token" in response.get_data(as_text=True)


        def test_admin_login_accepts_local_scaffold_token(tmp_path):
            app = Flask(__name__)
            setup_visiondirector(app, project_root=tmp_path)

            client = app.test_client()
            response = client.post(
                "/visiondirector/admin/login",
                data={"token": ADMIN_TOKEN, "next": "/visiondirector/admin"},
            )

            assert response.status_code in {302, 303}
            assert "Set-Cookie" in response.headers

            admin_response = client.get("/visiondirector/admin")
            assert admin_response.status_code == 200
            assert "VisionDirector Admin Dashboard" in admin_response.get_data(as_text=True)
        '''
    )

admin_test_file.write_text(admin_tests, encoding="utf-8")
print("patched admin dashboard tests")


# ---------------------------------------------------------------------
# Patch smxCP tests
# ---------------------------------------------------------------------
smxcp_tests = smxcp_test_file.read_text(encoding="utf-8")

if "SMX_VISIONDIRECTOR_ADMIN_TOKEN=local-visiondirector-admin-token" not in smxcp_tests:
    smxcp_tests += dedent(
        '''


        def test_smxcp_local_env_contains_admin_token(tmp_path):
            scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)

            content = scaffold.env_file.read_text(encoding="utf-8")

            assert "SMX_VISIONDIRECTOR_ADMIN_TOKEN=local-visiondirector-admin-token" in content


        def test_smxcp_deploy_env_example_contains_admin_token_secret_mapping(tmp_path):
            scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)

            content = scaffold.deploy_env_example_file.read_text(encoding="utf-8")

            assert "SMX_VISIONDIRECTOR_ADMIN_TOKEN=visiondirector-admin-token-secret-vault:latest" in content
        '''
    )

smxcp_test_file.write_text(smxcp_tests, encoding="utf-8")
print("patched smxCP admin token tests")
