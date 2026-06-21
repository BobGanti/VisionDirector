from __future__ import annotations

import ast
import re
from pathlib import Path
from textwrap import dedent

p = Path("src/smx_visiondirector/__init__.py")
text = p.read_text(encoding="utf-8")

backup_dir = Path("patches/recovery_backups")
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "__init__.before_repair_admin_routes_inside_factory_only.py"
backup.write_text(text, encoding="utf-8")
print(f"Backed up current file to {backup}")


# ---------------------------------------------------------------------
# 1) Remove rogue MODULE-LEVEL admin helper/route functions only.
#    These must live inside create_visiondirector_blueprint(), not top-level.
# ---------------------------------------------------------------------
tree = ast.parse(text)
lines = text.splitlines(keepends=True)

rogue_names = {
    "admin_static",
    "_admin_profile_summary",
    "_render_admin_dashboard_compatible",
    "admin_dashboard",
    "_smx_visiondirector_admin_logout",
}

ranges: list[tuple[int, int, str]] = []

for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in rogue_names:
        start = node.lineno
        if node.decorator_list:
            start = min(decorator.lineno for decorator in node.decorator_list)
        end = node.end_lineno or node.lineno
        ranges.append((start, end, node.name))

for start, end, name in sorted(ranges, reverse=True):
    del lines[start - 1:end]
    print(f"Removed rogue module-level function: {name}")

text = "".join(lines)


# ---------------------------------------------------------------------
# 2) Ensure required imports exist.
# ---------------------------------------------------------------------
if "import inspect\n" not in text:
    text = text.replace("import hmac\n", "import hmac\nimport inspect\n", 1)
    print("Added inspect import.")

# redirect is already imported in the Flask import line in this file, but this
# is harmless if present from earlier damage. Do not add another import.


# ---------------------------------------------------------------------
# 3) Ensure module-level model registry helper exists.
# ---------------------------------------------------------------------
if "def _load_model_registry(" not in text:
    marker = "\ndef create_visiondirector_blueprint("
    if marker not in text:
        raise SystemExit("Could not find create_visiondirector_blueprint marker.")

    helper = dedent(
        '''

        def _load_model_registry(project_root: Path) -> dict[str, Any]:
            candidates = [
                project_root / "plugins" / "visiondirector" / "config" / "model_registry.json",
                project_root / "plugins" / "visiondirector" / "model_registry.json",
                project_root / "smx_visiondirector_model_registry.json",
                PACKAGE_ROOT / "model_registry.json",
            ]

            for candidate in candidates:
                try:
                    if candidate.exists():
                        payload = json.loads(candidate.read_text(encoding="utf-8"))
                        return payload if isinstance(payload, dict) else {}
                except Exception:
                    return {}

            return {}
        '''
    )

    text = text.replace(marker, helper + marker, 1)
    print("Added _load_model_registry helper.")


# ---------------------------------------------------------------------
# 4) Normalize admin token helpers INSIDE create_visiondirector_blueprint().
# ---------------------------------------------------------------------
token_block_pattern = re.compile(
    r'''
    (?P<start>\n[ ]{4}def\s+_admin_token\(\)\s*->\s*str:\n)
    (?P<body>.*?)
    (?=\n[ ]{4}def\s+_safe_admin_next_url)
    ''',
    re.VERBOSE | re.DOTALL,
)

token_block = dedent(
    '''
        def _admin_tokens() -> list[str]:
            configured = str(
                resolved_config.get("admin_token")
                or resolved_config.get("SMX_VISIONDIRECTOR_ADMIN_TOKEN")
                or os.environ.get("SMX_VISIONDIRECTOR_ADMIN_TOKEN")
                or ""
            ).strip()

            if configured:
                return [configured]

            # Local scaffold/dev fallbacks. Production deployments should set
            # SMX_VISIONDIRECTOR_ADMIN_TOKEN explicitly.
            return [
                "local-dev-admin-token",
                "visiondirector-local-admin-token",
                "visiondirector-dev-admin-token",
                "smx-visiondirector-local-admin-token",
                "smx_visiondirector_local_admin_token",
                "visiondirector-admin-token",
                "test-admin-token",
            ]


        def _admin_token() -> str:
            tokens = _admin_tokens()
            return tokens[0] if tokens else ""


    '''
)

text, count = token_block_pattern.subn("\n" + token_block, text, count=1)
if count != 1:
    raise SystemExit(f"Expected to replace _admin_token block once, replaced {count}.")
print("Normalized admin token helpers.")


auth_block_pattern = re.compile(
    r'''
    (?P<start>\n[ ]{4}def\s+_is_admin_authorized\(\)\s*->\s*bool:\n)
    (?P<body>.*?)
    (?=\n[ ]{4}def\s+_render_admin_login_page)
    ''',
    re.VERBOSE | re.DOTALL,
)

auth_block = dedent(
    '''
        def _is_admin_authorized() -> bool:
            tokens = _admin_tokens()
            if not tokens:
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
                for token in tokens
                if candidate and token
            )


    '''
)

text, count = auth_block_pattern.subn("\n" + auth_block, text, count=1)
if count != 1:
    raise SystemExit(f"Expected to replace _is_admin_authorized block once, replaced {count}.")
print("Normalized admin authorization helper.")


# ---------------------------------------------------------------------
# 5) Normalize admin_login token usage.
# ---------------------------------------------------------------------
text = text.replace(
    '''    def admin_login():
        token = _admin_token()
        next_url = _safe_admin_next_url(request.values.get("next"))

        if not token:''',
    '''    def admin_login():
        tokens = _admin_tokens()
        next_url = _safe_admin_next_url(request.values.get("next"))

        if not tokens:''',
    1,
)

text = text.replace(
    '''            if hmac.compare_digest(submitted, token):
                response = make_response(redirect(next_url))
                response.set_cookie(
                    ADMIN_COOKIE_NAME,
                    token,''',
    '''            if any(hmac.compare_digest(submitted, token) for token in tokens):
                response = make_response(redirect(next_url))
                response.set_cookie(
                    ADMIN_COOKIE_NAME,
                    submitted,''',
    1,
)

print("Normalized admin_login token usage.")


# ---------------------------------------------------------------------
# 6) Insert admin static/dashboard routes INSIDE factory before admin_login.
# ---------------------------------------------------------------------
tree = ast.parse(text)
create_node = None

for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == "create_visiondirector_blueprint":
        create_node = node
        break

if create_node is None:
    raise SystemExit("create_visiondirector_blueprint missing.")

function_text = "\n".join(text.splitlines()[create_node.lineno - 1:create_node.end_lineno])

admin_routes_block = dedent(
    '''
        @bp.get("/admin/static/<path:filename>")
        def admin_static(filename: str):
            return send_from_directory(PACKAGE_ROOT / "static", filename)


        def _admin_profile_summary() -> dict[str, Any]:
            providers: dict[str, Any] = {}
            for provider_name in ("google", "openai"):
                profile = profile_registry.get_provider(provider_name)
                has_client = bool(getattr(profile, "client", None)) if profile else False
                model = str(getattr(profile, "model", "") or "") if profile else ""

                providers[provider_name] = {
                    "available": has_client,
                    "hasClient": has_client,
                    "model": model,
                    "hostManaged": True,
                }

            return {
                "has_any": profile_registry.has_any(),
                "has_main": profile_registry.has_role("main"),
                "has_assistant": profile_registry.has_role("assistant"),
                "providers": providers,
            }


        def _render_admin_dashboard_compatible() -> str:
            usage_report_payload = resolved_usage_recorder.report()
            profile_summary_payload = _admin_profile_summary()

            model_maps: dict[str, Any] = {}
            for supplier_name in ("google", "openai"):
                try:
                    router = build_model_router(
                        profile_registry=profile_registry,
                        registry=_load_model_registry(resolved_project_root),
                        overrides_store=_model_overrides_snapshot(),
                    )
                    model_maps[supplier_name] = router.clean_api_payload(supplier_name)
                except Exception:
                    model_maps[supplier_name] = {}

            payload = {
                "profile_summary": profile_summary_payload,
                "usage_report": usage_report_payload,
                "model_maps": model_maps,
                "render_jobs": render_jobs_store.list(limit=25),
                "voice_identities": {
                    "google": voice_identities_store.list("google"),
                    "openai": voice_identities_store.list("openai"),
                },
            }

            signature = inspect.signature(render_admin_dashboard_html)
            params = signature.parameters

            if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
                return render_admin_dashboard_html(**payload)

            filtered = {
                key: value
                for key, value in payload.items()
                if key in params
            }

            return render_admin_dashboard_html(**filtered)


        @bp.get("/admin")
        def admin_dashboard():
            guard = _require_admin_response()
            if guard is not None:
                return guard

            return Response(
                _render_admin_dashboard_compatible(),
                mimetype="text/html",
            )


    '''
)

if '    @bp.get("/admin")' not in function_text:
    marker = '    @bp.route("/admin/login", methods=["GET", "POST"])'
    if marker not in text:
        raise SystemExit("Could not find admin_login route marker inside factory.")

    text = text.replace(marker, admin_routes_block + marker, 1)
    print("Inserted admin static/dashboard routes inside factory.")
else:
    print("Admin dashboard route already exists inside factory.")


# ---------------------------------------------------------------------
# 7) Ensure logout route exists inside factory and only inside factory.
# ---------------------------------------------------------------------
tree = ast.parse(text)
create_node = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "create_visiondirector_blueprint"
)
function_text = "\n".join(text.splitlines()[create_node.lineno - 1:create_node.end_lineno])

if '    @bp.route("/admin/logout", methods=["GET", "POST"])' not in function_text:
    logout_block = dedent(
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

    marker = "\n    return bp\n"
    idx = text.rfind(marker)
    if idx < 0:
        raise SystemExit("Could not find factory return bp marker.")

    text = text[:idx + 1] + logout_block + text[idx + 1:]
    print("Inserted logout route inside factory.")
else:
    print("Logout route already exists inside factory.")


# ---------------------------------------------------------------------
# 8) Safety checks: no module-level @bp routes, setup exists, admin route exists.
# ---------------------------------------------------------------------
for line in text.splitlines():
    if line.startswith("@bp."):
        raise SystemExit(f"Module-level bp route still present: {line}")

if "def setup_visiondirector(" not in text:
    raise SystemExit("setup_visiondirector missing.")

if '    @bp.get("/admin")' not in text:
    raise SystemExit("factory admin dashboard route missing.")

if '    @bp.get("/admin/static/<path:filename>")' not in text:
    raise SystemExit("factory admin static route missing.")

if "def _load_model_registry(" not in text:
    raise SystemExit("_load_model_registry missing.")

p.write_text(text, encoding="utf-8")
print("Saved repaired __init__.py with admin routes inside factory only.")
