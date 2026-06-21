from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
target = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not target.exists():
    raise SystemExit("Missing src/smx_visiondirector/__init__.py. Run from VisionDirector root.")

target.write_text(
    dedent(
        r'''
        from __future__ import annotations

        import json
        import os
        from pathlib import Path
        from typing import Any
        from uuid import uuid4

        from flask import Blueprint, Response, request, send_from_directory, url_for

        from .smxcp import SmxVisionDirectorScaffold, ensure_visiondirector_scaffold


        __version__ = "0.1.0"

        PACKAGE_ROOT = Path(__file__).resolve().parent
        PROJECT_ROOT = PACKAGE_ROOT.parents[1]
        DEFAULT_URL_PREFIX = "/visiondirector"


        def create_visiondirector_blueprint(
            *,
            config: dict[str, Any] | None = None,
            project_root: str | Path | None = None,
            ai_profile: dict[str, Any] | None = None,
        ) -> Blueprint:
            resolved_config = config or {}
            resolved_project_root = Path(project_root or PROJECT_ROOT).resolve()

            settings_store = {
                "supplier": "google",
                "ui_scale": "normal",
                "theme": "dark",
            }
            model_overrides_store: dict[str, dict[str, str]] = {
                "google": {},
                "openai": {},
            }
            voice_identities_store: dict[str, list[dict[str, Any]]] = {
                "google": [],
                "openai": [],
            }

            bp = Blueprint("smx_visiondirector", __name__)

            @bp.get("/health")
            def health():
                profile = ai_profile or {}
                return {
                    "status": "ok",
                    "package": "smx-visiondirector",
                    "has_ai_profile": bool(profile),
                    "has_main_profile": "main" in profile,
                    "has_assistant_profile": "assistant" in profile,
                }

            @bp.get("/api/credentials/status")
            def credentials_status():
                return {
                    "status": {
                        "google": _profile_has_supplier(ai_profile, "google"),
                        "openai": _profile_has_supplier(ai_profile, "openai"),
                    },
                    "hostManaged": True,
                }

            @bp.route("/api/credentials/<supplier>", methods=["GET", "POST", "DELETE"])
            def credentials_supplier(supplier: str):
                supplier = supplier.strip().lower()
                if supplier not in {"google", "openai"}:
                    return {"error": "unsupported supplier"}, 404

                if request.method == "GET":
                    return {
                        "supplier": supplier,
                        "available": _profile_has_supplier(ai_profile, supplier),
                        "apiKey": "",
                        "hostManaged": True,
                    }

                return {
                    "ok": False,
                    "hostManaged": True,
                    "message": (
                        "Credentials are owned by the SyntaxMatrix host and are not "
                        "stored by the browser plugin."
                    ),
                }, 409

            @bp.route("/api/settings/supplier", methods=["GET", "POST"])
            def setting_supplier():
                if request.method == "POST":
                    payload = request.get_json(silent=True) or {}
                    supplier = str(payload.get("supplier") or "").strip().lower()
                    if supplier not in {"google", "openai"}:
                        return {"error": "unsupported supplier"}, 400
                    settings_store["supplier"] = supplier

                return {"supplier": settings_store["supplier"]}

            @bp.route("/api/settings/ui-scale", methods=["GET", "POST"])
            def setting_ui_scale():
                if request.method == "POST":
                    payload = request.get_json(silent=True) or {}
                    ui_scale = str(payload.get("uiScale") or "").strip().lower()
                    if ui_scale not in {"normal", "large"}:
                        return {"error": "unsupported uiScale"}, 400
                    settings_store["ui_scale"] = ui_scale

                return {"uiScale": settings_store["ui_scale"]}

            @bp.route("/api/settings/theme", methods=["GET", "POST"])
            def setting_theme():
                if request.method == "POST":
                    payload = request.get_json(silent=True) or {}
                    theme = str(payload.get("theme") or "").strip().lower()
                    if theme not in {"dark", "light"}:
                        return {"error": "unsupported theme"}, 400
                    settings_store["theme"] = theme

                return {"theme": settings_store["theme"]}

            @bp.get("/api/model-overrides/<supplier>")
            def model_overrides_get(supplier: str):
                supplier = supplier.strip().lower()
                registry = _load_model_registry(resolved_project_root)
                defaults = (
                    registry.get("suppliers", {})
                    .get(supplier, {})
                    .get("defaults", {})
                )
                keys = registry.get("agencies") or sorted(defaults)

                return {
                    "supplier": supplier,
                    "defaults": defaults,
                    "keys": keys,
                    "overrides": model_overrides_store.setdefault(supplier, {}),
                }

            @bp.post("/api/model-overrides/<supplier>")
            def model_overrides_post(supplier: str):
                supplier = supplier.strip().lower()
                payload = request.get_json(silent=True) or {}
                overrides = payload.get("overrides") or {}

                if not isinstance(overrides, dict):
                    return {"error": "overrides must be an object"}, 400

                clean = {
                    str(key): str(value).strip()
                    for key, value in overrides.items()
                    if str(value).strip()
                }
                model_overrides_store[supplier] = clean

                return {"supplier": supplier, "overrides": clean}

            @bp.post("/api/model-overrides/<supplier>/reset")
            def model_overrides_reset(supplier: str):
                supplier = supplier.strip().lower()
                model_overrides_store[supplier] = {}
                return {"supplier": supplier, "overrides": {}}

            @bp.route("/api/voice-identities/<supplier>", methods=["GET", "POST"])
            def voice_identities(supplier: str):
                supplier = supplier.strip().lower()
                if supplier not in voice_identities_store:
                    voice_identities_store[supplier] = []

                if request.method == "GET":
                    return {
                        "supplier": supplier,
                        "voices": voice_identities_store[supplier],
                    }

                payload = request.get_json(silent=True) or {}
                voice = {
                    "id": uuid4().hex,
                    "supplier": supplier,
                    "label": str(payload.get("label") or "VOICE").upper(),
                    "baseVoice": str(payload.get("baseVoice") or "Zephyr"),
                    "traits": str(payload.get("traits") or ""),
                    "speed": str(payload.get("speed") or "natural"),
                    "sentiment": payload.get("sentiment"),
                }
                voice_identities_store[supplier].insert(0, voice)

                return {"supplier": supplier, "voice": voice}

            @bp.delete("/api/voice-identities/<supplier>/<voice_id>")
            def voice_identity_delete(supplier: str, voice_id: str):
                supplier = supplier.strip().lower()
                current = voice_identities_store.setdefault(supplier, [])
                voice_identities_store[supplier] = [
                    voice for voice in current if voice.get("id") != voice_id
                ]
                return {"ok": True}

            @bp.get("/assets/<path:filename>")
            def asset(filename: str):
                assets_dir = Path(
                    resolved_config.get("assets_dir")
                    or "plugins/visiondirector/assets"
                )
                if not assets_dir.is_absolute():
                    assets_dir = Path.cwd() / assets_dir

                return send_from_directory(assets_dir, filename)

            @bp.get("/")
            def home():
                index_file = resolved_project_root / "index.html"
                if not index_file.exists():
                    return Response("VisionDirector index.html not found.", status=500)

                html = index_file.read_text(encoding="utf-8")
                html = _inject_safe_runtime(
                    html,
                    config=resolved_config,
                    ai_profile=ai_profile,
                )
                html = _rewrite_index_asset_urls(html)
                return Response(html, mimetype="text/html")

            @bp.get("/<path:filename>")
            def static_file(filename: str):
                if filename == "index.js":
                    js_file = resolved_project_root / "index.js"
                    if not js_file.exists():
                        return Response("VisionDirector index.js not found.", status=500)

                    js = js_file.read_text(encoding="utf-8")
                    js = _rewrite_runtime_js_urls(js)
                    return Response(js, mimetype="application/javascript")

                return send_from_directory(resolved_project_root, filename)

            return bp


        def setup_visiondirector(
            app,
            *,
            project_root: str | Path | None = None,
            init_schema: bool = True,
            ai_profile: dict[str, Any] | None = None,
        ):
            scaffold = ensure_visiondirector_scaffold(project_root=project_root)
            config = _config_from_env_file(scaffold.env_file)

            return init_visiondirector(
                app,
                config=config,
                project_root=PROJECT_ROOT,
                init_schema=init_schema,
                ai_profile=ai_profile,
            )


        def init_visiondirector(
            app,
            *,
            config: dict[str, Any] | None = None,
            project_root: str | Path | None = None,
            init_schema: bool = False,
            ai_profile: dict[str, Any] | None = None,
        ):
            # init_schema is part of the SyntaxMatrix plugin contract.
            # VisionDirector has no package-owned schema yet, so this is a no-op.
            app.register_blueprint(
                create_visiondirector_blueprint(
                    config=config,
                    project_root=project_root,
                    ai_profile=ai_profile,
                ),
                url_prefix=DEFAULT_URL_PREFIX,
            )
            return app


        def _config_from_env_file(env_file: str | Path) -> dict[str, str]:
            values: dict[str, str] = {}
            path = Path(env_file)

            if path.exists():
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        values[key.strip()] = os.environ.get(key.strip(), value.strip())

            return {
                "host_site_title": values.get(
                    "SMX_VISIONDIRECTOR_HOST_SITE_TITLE",
                    "SyntaxMatrix",
                ),
                "host_home_url": values.get("SMX_VISIONDIRECTOR_HOST_HOME_URL", "/"),
                "app_title": values.get(
                    "SMX_VISIONDIRECTOR_APP_TITLE",
                    "VisionDirector",
                ),
                "app_home_url": values.get(
                    "SMX_VISIONDIRECTOR_APP_HOME_URL",
                    DEFAULT_URL_PREFIX,
                ),
                "assets_dir": values.get(
                    "SMX_VISIONDIRECTOR_ASSETS_DIR",
                    "plugins/visiondirector/assets",
                ),
                "logo_url": values.get(
                    "SMX_VISIONDIRECTOR_LOGO_URL",
                    "/visiondirector/assets/logo.png",
                ),
                "favicon_url": values.get(
                    "SMX_VISIONDIRECTOR_FAVICON_URL",
                    "/visiondirector/assets/favicon.png",
                ),
            }


        def _profile_has_supplier(
            ai_profile: dict[str, Any] | None,
            supplier: str,
        ) -> bool:
            profile = ai_profile or {}
            supplier = supplier.strip().lower()

            for value in profile.values():
                if (
                    isinstance(value, dict)
                    and str(value.get("provider") or "").lower() == supplier
                ):
                    return True

            direct = profile.get(supplier)
            return isinstance(direct, dict)


        def _load_model_registry(project_root: Path) -> dict[str, Any]:
            fallback = {
                "agencies": [
                    "SCRIPT_PARSER",
                    "DICTATION",
                    "VOICE_ANALYZER",
                    "AUTO_NARRATOR",
                    "IMAGE_GEN",
                    "VIDEO_GEN",
                    "TTS_PREVIEW",
                ],
                "suppliers": {
                    "google": {
                        "defaults": {
                            "SCRIPT_PARSER": "gemini-3-flash-preview",
                            "DICTATION": "gemini-3-flash-preview",
                            "VOICE_ANALYZER": "gemini-3-flash-preview",
                            "AUTO_NARRATOR": "gemini-3-flash-preview",
                            "IMAGE_GEN": "gemini-2.5-flash-image",
                            "VIDEO_GEN": "veo-3.1-generate-preview",
                            "TTS_PREVIEW": "gemini-2.5-flash-preview-tts",
                        },
                    },
                    "openai": {
                        "defaults": {
                            "SCRIPT_PARSER": "gpt-5-mini",
                            "DICTATION": "gpt-4o-mini-transcribe",
                            "VOICE_ANALYZER": "gpt-5.1-nano",
                            "AUTO_NARRATOR": "gpt-4.1-nano",
                            "IMAGE_GEN": "gpt-image-1",
                            "VIDEO_GEN": "sora-2",
                            "TTS_PREVIEW": "gpt-4o-mini-tts",
                        },
                    },
                },
            }

            registry_file = project_root / "shared" / "model_registry.json"
            if not registry_file.exists():
                return fallback

            try:
                return json.loads(registry_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return fallback


        def _inject_safe_runtime(
            html: str,
            *,
            config: dict[str, Any],
            ai_profile: dict[str, Any] | None,
        ) -> str:
            profile = ai_profile or {}
            runtime = {
                "appTitle": config.get("app_title") or "VisionDirector",
                "hostSiteTitle": config.get("host_site_title") or "SyntaxMatrix",
                "hostHomeUrl": config.get("host_home_url") or "/",
                "appHomeUrl": config.get("app_home_url") or DEFAULT_URL_PREFIX,
                "hasAiProfile": bool(profile),
                "hasMainProfile": "main" in profile,
                "hasAssistantProfile": "assistant" in profile,
            }

            script = (
                "<script>"
                "window.__SMX_VISIONDIRECTOR__ = "
                f"{json.dumps(runtime, sort_keys=True)};"
                "window.process = window.process || { env: {} };"
                "window.process.env = window.process.env || {};"
                "window.process.env.API_KEY = window.process.env.API_KEY || '';"
                "</script>"
            )

            return html.replace("<head>", f"<head>\n  {script}", 1)


        def _rewrite_runtime_js_urls(js: str) -> str:
            return (
                js.replace('"/api/', '"/visiondirector/api/')
                .replace("'/api/", "'/visiondirector/api/")
                .replace("`/api/", "`/visiondirector/api/")
            )


        def _rewrite_index_asset_urls(html: str) -> str:
            css_url = url_for("smx_visiondirector.static_file", filename="index.css")
            js_url = url_for("smx_visiondirector.static_file", filename="index.js")

            return (
                html.replace('href="/index.css"', f'href="{css_url}"')
                .replace("href='/index.css'", f"href='{css_url}'")
                .replace('src="/index.js"', f'src="{js_url}"')
                .replace("src='/index.js'", f"src='{js_url}'")
            )


        __all__ = [
            "DEFAULT_URL_PREFIX",
            "PACKAGE_ROOT",
            "PROJECT_ROOT",
            "SmxVisionDirectorScaffold",
            "__version__",
            "create_visiondirector_blueprint",
            "ensure_visiondirector_scaffold",
            "init_visiondirector",
            "setup_visiondirector",
        ]
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("fixed smx_visiondirector __init__.py runtime routes")
