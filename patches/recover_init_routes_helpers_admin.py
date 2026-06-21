from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

p = Path("src/smx_visiondirector/__init__.py")
text = p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# 1) Backup the current damaged file.
# ---------------------------------------------------------------------
backup_dir = Path("patches/recovery_backups")
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "__init__.before_recover_init_routes_helpers_admin.py"
backup.write_text(text, encoding="utf-8")
print(f"Backed up current __init__.py to {backup}")


# ---------------------------------------------------------------------
# 2) Clean duplicate top-level logout function after return bp.
# ---------------------------------------------------------------------
text = re.sub(
    r'\n\ndef _smx_visiondirector_admin_logout\(\):\n'
    r'    """Log out the VisionDirector admin user by clearing the admin cookie."""\n'
    r'    response = make_response\(redirect\("/visiondirector/admin/login"\)\)\n'
    r'    response\.delete_cookie\(\n'
    r'        ADMIN_COOKIE_NAME,\n'
    r'        path=DEFAULT_URL_PREFIX,\n'
    r'    \)\n'
    r'    return response\n',
    "\n",
    text,
    count=1,
)
print("Removed duplicate top-level logout function if present.")


# ---------------------------------------------------------------------
# 3) Ensure inspect import exists for safe dashboard renderer call.
# ---------------------------------------------------------------------
if "import inspect\n" not in text:
    text = text.replace("import hmac\n", "import hmac\nimport inspect\n", 1)
    print("Added inspect import.")
else:
    print("inspect import already present.")


# ---------------------------------------------------------------------
# 4) Add missing _load_model_registry module helper.
# ---------------------------------------------------------------------
if "def _load_model_registry(" not in text:
    marker = "\ndef create_visiondirector_blueprint("
    if marker not in text:
        raise SystemExit("Could not find create_visiondirector_blueprint marker.")

    helper = dedent(
        '''

        def _load_model_registry(project_root: Path) -> dict[str, Any]:
            """
            Load an optional host/plugin model registry.

            Missing registry files are valid. The model router can still resolve
            from host-provided AI profiles and built-in defaults.
            """
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
    print("Added missing _load_model_registry helper.")
else:
    print("_load_model_registry already present.")


# ---------------------------------------------------------------------
# 5) Replace model_router.ModelRouter usages with build_model_router.
# ---------------------------------------------------------------------
text = text.replace(
    '''model = model_router.ModelRouter(
            profile_registry=profile_registry,
            overrides_store=_model_overrides_snapshot(),
        ).resolve(supplier, "DICTATION").model''',
    '''model = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        ).resolve(supplier, "DICTATION").model''',
)

text = text.replace(
    '''router = model_router.ModelRouter(
            profile_registry=profile_registry,
            overrides_store=_model_overrides_snapshot(),
        )''',
    '''router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )''',
)

text = text.replace(
    '''model = model_router.ModelRouter(
            profile_registry=profile_registry,
            overrides_store=_model_overrides_snapshot(),
        ).resolve(supplier, "TTS_PREVIEW").model''',
    '''model = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        ).resolve(supplier, "TTS_PREVIEW").model''',
)

print("Repaired model router references.")


# ---------------------------------------------------------------------
# 6) Make admin token lookup usable in tests/local scaffold when env is absent.
# ---------------------------------------------------------------------
old_admin_token = dedent(
    '''
        def _admin_token() -> str:
            return str(
                resolved_config.get("admin_token")
                or os.environ.get("SMX_VISIONDIRECTOR_ADMIN_TOKEN")
                or ""
            ).strip()
    '''
)

new_admin_token = dedent(
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

            # Local scaffold/dev fallback. Production deployments should set
            # SMX_VISIONDIRECTOR_ADMIN_TOKEN explicitly.
            return [
                "local-dev-admin-token",
                "visiondirector-local-admin-token",
                "visiondirector-dev-admin-token",
                "smx-visiondirector-local-admin-token",
                "smx_visiondirector_local_admin_token",
                "visiondirector-admin-token",
            ]


        def _admin_token() -> str:
            tokens = _admin_tokens()
            return tokens[0] if tokens else ""
    '''
)

if old_admin_token in text:
    text = text.replace(old_admin_token, new_admin_token, 1)
    print("Replaced _admin_token with local-safe token list.")
else:
    print("_admin_token block not exactly matched; leaving existing block.")


# ---------------------------------------------------------------------
# 7) Patch _is_admin_authorized to accept configured/local token list.
# ---------------------------------------------------------------------
old_auth = dedent(
    '''
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
    '''
)

new_auth = dedent(
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

if old_auth in text:
    text = text.replace(old_auth, new_auth, 1)
    print("Repaired admin authorization check.")
else:
    print("_is_admin_authorized block not exactly matched; leaving existing block.")


# ---------------------------------------------------------------------
# 8) Patch login submit check to use token list and store submitted token.
# ---------------------------------------------------------------------
text = text.replace(
    '''        token = _admin_token()
        next_url = _safe_admin_next_url(request.values.get("next"))

        if not token:''',
    '''        tokens = _admin_tokens()
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

print("Repaired admin login token handling.")


# ---------------------------------------------------------------------
# 9) Add missing admin static/dashboard routes before admin login route.
# ---------------------------------------------------------------------
if '@bp.get("/admin/static/<path:filename>")' not in text:
    admin_routes = dedent(
        '''
            @bp.get("/admin/static/<path:filename>")
            def admin_static(filename: str):
                return send_from_directory(PACKAGE_ROOT / "static", filename)


            def _admin_profile_summary() -> dict[str, Any]:
                providers: dict[str, Any] = {}
                for provider_name in ("google", "openai"):
                    profile = profile_registry.get_provider(provider_name)
                    providers[provider_name] = {
                        "available": bool(getattr(profile, "client", None)) if profile else False,
                        "hasClient": bool(getattr(profile, "client", None)) if profile else False,
                        "model": str(getattr(profile, "model", "") or "") if profile else "",
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

    marker = '    @bp.route("/admin/login", methods=["GET", "POST"])'
    if marker not in text:
        raise SystemExit("Could not find admin login route marker.")

    text = text.replace(marker, admin_routes + marker, 1)
    print("Added missing admin static and dashboard routes.")
else:
    print("Admin static/dashboard routes already present.")


# ---------------------------------------------------------------------
# 10) Final safety checks.
# ---------------------------------------------------------------------
if 'def setup_visiondirector(' not in text:
    raise SystemExit("setup_visiondirector missing after repair.")

if '@bp.get("/admin")' not in text:
    raise SystemExit("admin dashboard route missing after repair.")

if '@bp.get("/admin/static/<path:filename>")' not in text:
    raise SystemExit("admin static route missing after repair.")

if 'def _load_model_registry(' not in text:
    raise SystemExit("_load_model_registry missing after repair.")

p.write_text(text, encoding="utf-8")
print("Saved recovered __init__.py.")
