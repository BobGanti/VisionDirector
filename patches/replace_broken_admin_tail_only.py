from __future__ import annotations

from pathlib import Path
from textwrap import dedent

p = Path("src/smx_visiondirector/__init__.py")
text = p.read_text(encoding="utf-8")

backup_dir = Path("patches/recovery_backups")
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "__init__.before_replace_broken_admin_tail_only.py"
backup.write_text(text, encoding="utf-8")
print(f"Backed up current __init__.py to {backup}")

usage_block = '''    @bp.get("/api/usage/report")
    def usage_report():
        return resolved_usage_recorder.report()
'''

usage_pos = text.find(usage_block)
if usage_pos < 0:
    raise SystemExit("Could not find the exact usage_report block.")

tail_start = usage_pos + len(usage_block)

setup_marker = "\ndef setup_visiondirector("
setup_pos = text.find(setup_marker, tail_start)
if setup_pos < 0:
    raise SystemExit("Could not find setup_visiondirector after usage_report.")

clean_admin_tail = dedent(
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


        @bp.route("/admin/logout", methods=["GET", "POST"])
        def admin_logout():
            response = make_response(redirect("/visiondirector/admin/login"))
            response.delete_cookie(
                ADMIN_COOKIE_NAME,
                path=DEFAULT_URL_PREFIX,
            )
            return response


        return bp

    '''
)

text = text[:tail_start] + "\n\n" + clean_admin_tail + text[setup_pos:]

# Safety checks before writing.
if "\n@bp." in text:
    raise SystemExit("Module-level @bp route still exists; refusing to write.")

if '    @bp.get("/admin")' not in text:
    raise SystemExit("Factory-level admin route missing.")

if '    @bp.route("/admin/login", methods=["GET", "POST"])' not in text:
    raise SystemExit("Factory-level admin login route missing.")

if '    @bp.route("/admin/logout", methods=["GET", "POST"])' not in text:
    raise SystemExit("Factory-level admin logout route missing.")

if "\n    return bp\n" not in text:
    raise SystemExit("Factory return bp missing.")

p.write_text(text, encoding="utf-8")
print("Replaced broken admin tail with clean factory-level admin routes.")
