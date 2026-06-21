from __future__ import annotations

from flask import redirect, session

import hmac
import inspect
import json
import os
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import Blueprint, Response, make_response, redirect, request, send_from_directory, url_for

from .admin_dashboard import render_admin_dashboard_html
from .ai_profiles import AIProfileRegistry, VisionDirectorAIProfileError, build_ai_profile_registry
from .ai_runtime import VisionDirectorAIExecutionError, build_ai_runtime
from .model_router import build_model_router
from .storage import SQLiteModelOverridesStore, SQLiteRenderJobStore, SQLiteVoiceIdentityStore, VisionDirectorStorage, build_storage_from_database_url
from .usage import (
    InMemoryUsageRecorder,
    JsonlUsageRecorder,
    SQLiteUsageRecorder,
    UsageRecorder,
)
from .smxcp import SmxVisionDirectorScaffold, ensure_visiondirector_scaffold


__version__ = "0.1.0"

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
DEFAULT_URL_PREFIX = "/visiondirector"
ADMIN_COOKIE_NAME = "smx_visiondirector_admin_token"



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


def _config_from_env_file(env_file: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    path = Path(env_file)

    if path.exists():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                values[key] = os.environ.get(key, value.strip())

    return {
        "public_base_url": values.get("SMX_VISIONDIRECTOR_PUBLIC_BASE_URL", ""),
        "host_site_title": values.get("SMX_VISIONDIRECTOR_HOST_SITE_TITLE", "SyntaxMatrix"),
        "host_home_url": values.get("SMX_VISIONDIRECTOR_HOST_HOME_URL", "/"),
        "app_title": values.get("SMX_VISIONDIRECTOR_APP_TITLE", "VisionDirector"),
        "app_home_url": values.get("SMX_VISIONDIRECTOR_APP_HOME_URL", DEFAULT_URL_PREFIX),
        "database_backend": values.get("SMX_VISIONDIRECTOR_DATABASE_BACKEND", "sqlite"),
        "SMX_VISIONDIRECTOR_DATABASE_URL": values.get(
            "SMX_VISIONDIRECTOR_DATABASE_URL",
            os.environ.get("SMX_VISIONDIRECTOR_DATABASE_URL", ""),
        ),
        "assets_dir": values.get("SMX_VISIONDIRECTOR_ASSETS_DIR", "plugins/visiondirector/assets"),
        "data_dir": values.get("SMX_VISIONDIRECTOR_DATA_DIR", "plugins/visiondirector/data"),
        "logo_url": values.get("SMX_VISIONDIRECTOR_LOGO_URL", "/visiondirector/assets/logo.png"),
        "favicon_url": values.get("SMX_VISIONDIRECTOR_FAVICON_URL", "/visiondirector/assets/favicon.png"),
        "admin_token": values.get(
            "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
            os.environ.get("SMX_VISIONDIRECTOR_ADMIN_TOKEN", ""),
        ),
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN": values.get(
            "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
            os.environ.get("SMX_VISIONDIRECTOR_ADMIN_TOKEN", ""),
        ),
    }


def _script_parser_prompt(prompt: str) -> str:
    return (
        "You are VisionDirector Script Intelligence. "
        "Return JSON only with exactly two string keys: visuals and narration. "
        "If narration is absent, use an empty string. "
        "If visuals are absent, create concise cinematic visuals.\n\n"
        f"USER_INPUT:\n{prompt}"
    )


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]


def _coerce_parsed_script(text: str, *, fallback_prompt: str) -> dict[str, str]:
    raw = str(text or "").strip()
    data: dict[str, Any] = {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        extracted = _extract_json_object(raw)
        if extracted:
            try:
                data = json.loads(extracted)
            except json.JSONDecodeError:
                data = {}

    return {
        "visuals": str(data.get("visuals") or fallback_prompt or "").strip(),
        "narration": str(data.get("narration") or "").strip(),
    }


def _visiondirector_runtime_js_patch() -> str:
    lines = [
        "",
        "// smx-visiondirector host AI patch.",
        "async function __smxVisionDirectorParseScript(prompt, supplier) {",
        "  const res = await fetch(\"/visiondirector/api/ai/parse-script\", {",
        "    method: \"POST\",",
        "    headers: { \"Content-Type\": \"application/json\" },",
        "    body: JSON.stringify({ prompt, supplier })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) throw new Error(data?.error || `VISIONDIRECTOR_PARSE_SCRIPT_FAILED: ${res.status}`);",
        "  return { visuals: String(data?.visuals || \"\"), narration: String(data?.narration || \"\") };",
        "}",
        "",
        "async function __smxVisionDirectorGenerateImage(prompt, aspectRatio, supplier) {",
        "  const res = await fetch(\"/visiondirector/api/ai/generate-image\", {",
        "    method: \"POST\",",
        "    headers: { \"Content-Type\": \"application/json\" },",
        "    body: JSON.stringify({ prompt, aspectRatio, supplier })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) throw new Error(data?.error || `VISIONDIRECTOR_GENERATE_IMAGE_FAILED: ${res.status}`);",
        "  return data?.imageDataUrl || null;",
        "}",
        "",
        "async function __smxVisionDirectorTranscribeAudio(audioBase64, supplier) {",
        "  const res = await fetch(\"/visiondirector/api/ai/transcribe-audio\", {",
        "    method: \"POST\",",
        "    headers: { \"Content-Type\": \"application/json\" },",
        "    body: JSON.stringify({ supplier, audioBase64 })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) throw new Error(data?.error || `VISIONDIRECTOR_TRANSCRIBE_AUDIO_FAILED: ${res.status}`);",
        "  return String(data?.text || \"\");",
        "}",
        "",
        "async function __smxVisionDirectorAnalyzeVoice(audioBase64, sentiment, supplier) {",
        "  const res = await fetch(\"/visiondirector/api/ai/analyze-voice\", {",
        "    method: \"POST\",",
        "    headers: { \"Content-Type\": \"application/json\" },",
        "    body: JSON.stringify({ supplier, audioBase64, sentiment })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) throw new Error(data?.error || `VISIONDIRECTOR_ANALYZE_VOICE_FAILED: ${res.status}`);",
        "  return String(data?.traits || \"\");",
        "}",
        "",
        "async function __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, supplier) {",
        "  const res = await fetch(\"/visiondirector/api/ai/generate-video\", {",
        "    method: \"POST\",",
        "    headers: { \"Content-Type\": \"application/json\" },",
        "    body: JSON.stringify({ supplier, visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) throw new Error(data?.error || `VISIONDIRECTOR_GENERATE_VIDEO_FAILED: ${res.status}`);",
        "  return { url: data?.url || \"\", videoRef: data?.videoRef || null };",
        "}",
        "",
        "async function __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, supplier) {",
        "  const res = await fetch(\"/visiondirector/api/ai/preview-voice\", {",
        "    method: \"POST\",",
        "    headers: { \"Content-Type\": \"application/json\" },",
        "    body: JSON.stringify({ supplier, voice, speed, traits, text })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) throw new Error(data?.error || `VISIONDIRECTOR_VOICE_PREVIEW_FAILED: ${res.status}`);",
        "  const audioUrl = data?.audioUrl;",
        "  if (!audioUrl) throw new Error(\"VISIONDIRECTOR_VOICE_PREVIEW_NO_AUDIO\");",
        "  const audio = new Audio(audioUrl);",
        "  await audio.play();",
        "}",
        "",
        "// speechSynthesis BROWSER_TTS_UNAVAILABLE browser fallback is intentionally bypassed; provider-backed backend preview is used.",
        "async function __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, supplier) {",
        "  return __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, supplier);",
        "}",
        "",
        "try {",
        "  if (typeof googleProvider !== \"undefined\") {",
        "    googleProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, \"google\");",
        "    googleProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, \"google\");",
        "    googleProvider.analyzeVoice = (audioBase64, sentiment) => __smxVisionDirectorAnalyzeVoice(audioBase64, sentiment, \"google\");",
        "    googleProvider.transcribeAudio = (audioBase64) => __smxVisionDirectorTranscribeAudio(audioBase64, \"google\");",
        "    googleProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, \"google\");",
        "    googleProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, \"google\");",
        "  }",
        "  if (typeof openaiProvider !== \"undefined\") {",
        "    openaiProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, \"openai\");",
        "    openaiProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, \"openai\");",
        "    openaiProvider.analyzeVoice = (audioBase64, sentiment) => __smxVisionDirectorAnalyzeVoice(audioBase64, sentiment, \"openai\");",
        "    openaiProvider.transcribeAudio = (audioBase64) => __smxVisionDirectorTranscribeAudio(audioBase64, \"openai\");",
        "    openaiProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, \"openai\");",
        "    openaiProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, \"openai\");",
        "  }",
        "} catch (error) {",
        "  console.warn(\"[smx-visiondirector] Failed to install host AI provider patch\", error);",
        "}",
        "",
        "// __smxVisionDirectorProviderVoicePreviewFinalOverride",
        "try {",
        "  if (typeof googleProvider !== \"undefined\") {",
        "    googleProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, \"google\");",
        "  }",
        "  if (typeof openaiProvider !== \"undefined\") {",
        "    openaiProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, \"openai\");",
        "  }",
        "} catch (error) {",
        "  console.warn(\"[smx-visiondirector] Failed to install final provider-backed voice preview patch\", error);",
        "}",
    ]
    return "\n".join(lines)

def create_visiondirector_blueprint(
    *,
    config: dict[str, Any] | None = None,
    project_root: str | Path | None = None,
    ai_profile: dict[str, Any] | None = None,
    usage_recorder: UsageRecorder | None = None,
    storage: VisionDirectorStorage | None = None,
) -> Blueprint:
    resolved_config = config or {}
    resolved_project_root = Path(project_root or PROJECT_ROOT).resolve()

    resolved_storage = storage

    if resolved_storage is None:

        resolved_storage = build_storage_from_database_url(

            str(resolved_config.get("SMX_VISIONDIRECTOR_DATABASE_URL") or ""),

            fallback_sqlite_path=resolved_project_root

            / "plugins"

            / "visiondirector"

            / "data"

            / "smx_visiondirector_dev.db",

        )

        resolved_storage.initialize()
    profile_registry = build_ai_profile_registry(ai_profile)
    resolved_usage_recorder = usage_recorder or JsonlUsageRecorder(
        resolved_project_root / "plugins" / "visiondirector" / "data" / "usage_events.jsonl"
    )

    settings_store = {
        "supplier": "google",
        "ui_scale": "normal",
        "theme": "dark",
    }
    model_overrides_store = SQLiteModelOverridesStore(resolved_storage)
    def _model_overrides_snapshot() -> dict[str, dict[str, str]]:
        if hasattr(model_overrides_store, "to_dict"):
            return model_overrides_store.to_dict()
        return model_overrides_store
    voice_identities_store = SQLiteVoiceIdentityStore(resolved_storage)
    render_jobs_store = SQLiteRenderJobStore(resolved_storage)

    bp = Blueprint("smx_visiondirector", __name__)

    def _resolve_current_model(task_key: str, supplier: str) -> str | None:
        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )
        resolved = router.resolve(supplier, task_key)
        return resolved.model or None




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
            "local-visiondirector-admin-token",
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


    def _safe_admin_next_url(value: str | None) -> str:
        candidate = str(value or "").strip()
        if candidate.startswith("/visiondirector/admin"):
            return candidate
        if candidate.startswith("/admin"):
            return candidate
        return url_for(".admin_dashboard")



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


    @bp.get("/health")
    def health():
        return {
            "status": "ok",
            "package": "smx-visiondirector",
            "has_ai_profile": profile_registry.has_any(),
            "has_main_profile": profile_registry.has_role("main"),
            "has_assistant_profile": profile_registry.has_role("assistant"),
        }




    def _rewrite_runtime_js_urls(js: str) -> str:
        rewritten = (
            js.replace('\"/api/', '\"/visiondirector/api/')
            .replace("'/api/", "'/visiondirector/api/")
            .replace("`/api/", "`/visiondirector/api/")
        )

        if "__smxVisionDirectorParseScript" not in rewritten:
            rewritten = f"{rewritten}\n{_visiondirector_runtime_js_patch()}\n"

        return rewritten

    def _rewrite_index_asset_urls(html: str) -> str:
        return (
            html.replace('src="/index.js"', 'src="/visiondirector/index.js"')
            .replace("src='/index.js'", "src='/visiondirector/index.js'")
            .replace('href="/index.css"', 'href="/visiondirector/index.css"')
            .replace("href='/index.css'", "href='/visiondirector/index.css'")
        )


    def _inject_safe_runtime(
        html: str,
        *,
        config: dict[str, Any],
        profile_registry: AIProfileRegistry,
    ) -> str:
        runtime = {
            "appTitle": config.get("app_title") or "VisionDirector",
            "hostSiteTitle": config.get("host_site_title") or "SyntaxMatrix",
            "hostHomeUrl": config.get("host_home_url") or "/",
            "appHomeUrl": config.get("app_home_url") or DEFAULT_URL_PREFIX,
            "hasAiProfile": profile_registry.has_any(),
            "hasMainProfile": profile_registry.has_role("main"),
            "hasAssistantProfile": profile_registry.has_role("assistant"),
            "aiProfile": profile_registry.safe_summary(),
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

    def _visiondirector_index_asset_path(filename: str) -> Path | None:
        candidates = [
            resolved_project_root / filename,
            Path.cwd() / filename,
            Path(__file__).resolve().parents[2] / filename,
        ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate

        return None


    @bp.get("/assets/<path:filename>")
    def asset(filename: str):
        assets_dir = Path(resolved_config.get("assets_dir") or "plugins/visiondirector/assets")
        if not assets_dir.is_absolute():
            assets_dir = resolved_project_root / assets_dir
        return send_from_directory(assets_dir, filename)


    @bp.get("/")
    def home():
        selected = _visiondirector_index_asset_path("index.html")
        if selected is None:
            return Response("VisionDirector index.html not found.", status=500, mimetype="text/plain")
        html = selected.read_text(encoding="utf-8")
        html = _inject_safe_runtime(html, config=resolved_config, profile_registry=profile_registry)
        html = _rewrite_index_asset_urls(html)
        return Response(html, mimetype="text/html")


    @bp.get("/index.js")
    def visiondirector_index_js_asset():
        selected = _visiondirector_index_asset_path("index.js")
        if selected is None:
            return Response(
                "VisionDirector index.js not found.",
                status=500,
                mimetype="text/plain",
            )

        js = selected.read_text(encoding="utf-8")
        js = _rewrite_runtime_js_urls(js)
        return Response(js, mimetype="application/javascript")


    @bp.get("/index.css")
    def visiondirector_index_css_asset():
        selected = _visiondirector_index_asset_path("index.css")
        if selected is None:
            return Response(
                "VisionDirector index.css not found.",
                status=500,
                mimetype="text/plain",
            )

        return Response(
            selected.read_text(encoding="utf-8"),
            mimetype="text/css",
        )


    @bp.get("/index.html")
    def visiondirector_index_html_asset():
        selected = _visiondirector_index_asset_path("index.html")
        if selected is None:
            return Response(
                "VisionDirector index.html not found.",
                status=500,
                mimetype="text/plain",
            )

        html = selected.read_text(encoding="utf-8")
        html = _inject_safe_runtime(
            html,
            config=resolved_config,
            profile_registry=profile_registry,
        )
        html = _rewrite_index_asset_urls(html)
        return Response(html, mimetype="text/html")

    def _host_provider_status_payload():
        providers = {}
        for provider_name in ("google", "openai"):
            profile = profile_registry.get_provider(provider_name)
            has_client = bool(getattr(profile, "client", None)) if profile else False
            model = str(getattr(profile, "model", "") or "") if profile else ""

            providers[provider_name] = {
                "available": has_client,
                "hostManaged": True,
                "source": "host_profile" if has_client else "missing",
                "model": model,
            }

        return {
            "google": providers["google"]["available"],
            "openai": providers["openai"]["available"],
            "status": {
                "google": providers["google"]["available"],
                "openai": providers["openai"]["available"],
            },
            "hostManaged": True,
            "managedBy": "syntaxmatrix_host",
            "message": "Credentials are managed by the SyntaxMatrix host. No browser API keys are required.",
            "providers": providers,
        }



    @bp.get("/api/credentials/status")
    def credentials_status():
        return _host_provider_status_payload()


    @bp.post("/api/credentials")
    def credentials_save_root():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or "").strip().lower()

        if supplier and supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        return {
            "ok": True,
            "hostManaged": True,
            "stored": False,
            "message": "Credentials are managed by the SyntaxMatrix host. The plugin did not store a browser API key.",
            "status": _host_provider_status_payload(),
        }


    @bp.route("/api/credentials/<supplier>", methods=["GET", "POST", "DELETE"])
    def credentials_supplier(supplier: str):
        supplier = supplier.strip().lower()
        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 404

        profile = profile_registry.get_provider(supplier)
        available = bool(getattr(profile, "client", None)) if profile else False
        model = str(getattr(profile, "model", "") or "") if profile else ""

        if request.method == "GET":
            return {
                "supplier": supplier,
                "available": available,
                "apiKey": "",
                "hostManaged": True,
                "managedBy": "syntaxmatrix_host",
                "model": model,
                "message": "Credentials are managed by the SyntaxMatrix host. No browser API key is exposed.",
            }

        if request.method == "POST":
            return {
                "ok": True,
                "supplier": supplier,
                "hostManaged": True,
                "stored": False,
                "message": "Credentials are managed by the SyntaxMatrix host. The plugin did not store a browser API key.",
                "status": _host_provider_status_payload(),
            }

        return {
            "ok": True,
            "supplier": supplier,
            "hostManaged": True,
            "deleted": False,
            "message": "Credentials are managed by the SyntaxMatrix host. There is no browser API key to delete.",
            "status": _host_provider_status_payload(),
        }


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
        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )
        return router.clean_api_payload(supplier)



    @bp.post("/api/model-overrides/<supplier>")
    def model_overrides_post(supplier: str):
        supplier = supplier.strip().lower()
        payload = request.get_json(silent=True) or {}
        overrides = payload.get("overrides") or {}

        if not isinstance(overrides, dict):
            return {"error": "overrides must be an object"}, 400

        clean = {
            str(key).strip().upper(): str(value).strip()
            for key, value in overrides.items()
            if str(key).strip() and str(value).strip()
        }
        model_overrides_store[supplier] = clean

        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )
        return router.clean_api_payload(supplier)



    @bp.post("/api/model-overrides/<supplier>/reset")
    def model_overrides_reset(supplier: str):
        supplier = supplier.strip().lower()
        model_overrides_store[supplier] = {}

        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )
        return router.clean_api_payload(supplier)


    @bp.get("/api/model-map/<supplier>")
    def current_model_map(supplier: str):
        supplier = supplier.strip().lower()
        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )
        return router.clean_api_payload(supplier)


    @bp.route("/api/voice-identities/<supplier>", methods=["GET", "POST"])
    def voice_identities(supplier: str):
        supplier = supplier.strip().lower()

        if request.method == "GET":
            return {
                "supplier": supplier,
                "voices": voice_identities_store.list(supplier),
            }

        payload = request.get_json(silent=True) or {}
        voice = voice_identities_store.create(
            {
                "id": uuid4().hex,
                "supplier": supplier,
                "label": str(payload.get("label") or "VOICE").upper(),
                "baseVoice": str(payload.get("baseVoice") or "Zephyr"),
                "traits": str(payload.get("traits") or ""),
                "speed": str(payload.get("speed") or "natural"),
                "sentiment": payload.get("sentiment"),
            }
        )

        return {"supplier": supplier, "voice": voice}

    @bp.delete("/api/voice-identities/<supplier>/<voice_id>")
    def voice_identity_delete(supplier: str, voice_id: str):
        supplier = supplier.strip().lower()
        deleted = voice_identities_store.delete(supplier, voice_id)
        return {"ok": True, "deleted": deleted}



    @bp.post("/api/ai/parse-script")
    def ai_parse_script():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or settings_store["supplier"]).strip().lower()
        prompt = str(payload.get("prompt") or "").strip()
        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("SCRIPT_PARSER", supplier)
        )

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        if not prompt:
            return {
                "visuals": "",
                "narration": "",
                "supplier": supplier,
                "model": model,
            }

        try:
            result = build_ai_runtime(profile_registry, usage_recorder=resolved_usage_recorder).generate_text_for_provider(
                operation="parse_script",
                provider=supplier,
                prompt=_script_parser_prompt(prompt),
                model=model,
            )
            parsed = _coerce_parsed_script(result.text, fallback_prompt=prompt)
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "visuals": parsed["visuals"],
            "narration": parsed["narration"],
            "supplier": result.provider,
            "model": result.model,
        }



    @bp.post("/api/ai/generate-image")
    def ai_generate_image():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or settings_store["supplier"]).strip().lower()
        prompt = str(payload.get("prompt") or "").strip()
        aspect_ratio = str(payload.get("aspectRatio") or "9:16").strip()
        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("IMAGE_GEN", supplier)
        )

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        try:
            result = build_ai_runtime(profile_registry, usage_recorder=resolved_usage_recorder).generate_image_for_provider(
                operation="generate_image",
                provider=supplier,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                model=model,
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "imageDataUrl": result.image_data_url,
            "supplier": result.provider,
            "model": result.model,
        }


    @bp.post("/api/ai/generate-text")
    def ai_generate_text():
        payload = request.get_json(silent=True) or {}
        role = str(payload.get("role") or "main").strip().lower()
        prompt = str(payload.get("prompt") or "").strip()
        model = str(payload.get("model") or "").strip() or None

        try:
            result = build_ai_runtime(profile_registry, usage_recorder=resolved_usage_recorder).generate_text(
                operation="generate_text",
                role=role,
                prompt=prompt,
                model=model,
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "role": result.role,
            "provider": result.provider,
            "model": result.model,
            "text": result.text,
        }




    @bp.get("/api/render-jobs")
    def render_jobs_list():
        limit = request.args.get("limit", 50)
        return {
            "jobs": render_jobs_store.list(limit=int(limit or 50)),
        }


    @bp.get("/api/render-jobs/<job_id>")
    def render_jobs_get(job_id: str):
        job = render_jobs_store.get(job_id)
        if not job:
            return {"error": "render job not found"}, 404
        return {"job": job}



    @bp.post("/api/ai/transcribe-audio")
    def ai_transcribe_audio():
        data = request.get_json(silent=True) or {}
        supplier = str(data.get("supplier") or "google").strip().lower()
        audio_base64 = str(
            data.get("audioBase64")
            or data.get("audioDataUrl")
            or data.get("audio")
            or ""
        )

        if not audio_base64:
            return {"error": "AUDIO_PAYLOAD_REQUIRED"}, 400

        model = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        ).resolve(supplier, "DICTATION").model

        try:
            result = build_ai_runtime(
                profile_registry,
                usage_recorder=resolved_usage_recorder,
            ).transcribe_audio_for_provider(
                provider=supplier,
                audio_base64=audio_base64,
                model=model,
                operation="transcribe_audio",
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "text": result.text,
            "supplier": result.provider,
            "model": result.model,
        }


    @bp.post("/api/ai/analyze-voice")
    def ai_analyze_voice():
        data = request.get_json(silent=True) or {}
        supplier = str(data.get("supplier") or "google").strip().lower()
        audio_base64 = str(
            data.get("audioBase64")
            or data.get("audioDataUrl")
            or data.get("audio")
            or ""
        )
        sentiment = str(data.get("sentiment") or "neutral")

        if not audio_base64:
            return {"error": "AUDIO_PAYLOAD_REQUIRED"}, 400

        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )
        model = router.resolve(supplier, "VOICE_ANALYZER").model
        dictation_model = router.resolve(supplier, "DICTATION").model

        try:
            result = build_ai_runtime(
                profile_registry,
                usage_recorder=resolved_usage_recorder,
            ).analyze_voice_for_provider(
                provider=supplier,
                audio_base64=audio_base64,
                sentiment=sentiment,
                model=model,
                dictation_model=dictation_model,
                operation="analyze_voice",
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "traits": result.text,
            "supplier": result.provider,
            "model": result.model,
        }



    @bp.post("/api/ai/preview-voice")
    def ai_preview_voice():
        data = request.get_json(silent=True) or {}
        supplier = str(data.get("supplier") or "google").strip().lower()
        voice = data.get("voice") or "Zephyr"
        speed = str(data.get("speed") or "natural")
        traits = str(data.get("traits") or "")
        text = str(data.get("text") or "Identity verified.")

        model = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        ).resolve(supplier, "TTS_PREVIEW").model

        try:
            result = build_ai_runtime(
                profile_registry,
                usage_recorder=resolved_usage_recorder,
            ).preview_voice_for_provider(
                provider=supplier,
                voice=voice,
                speed=speed,
                traits=traits,
                text=text,
                model=model,
                operation="voice_preview",
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "audioUrl": result["audio_url"],
            "supplier": result["provider"],
            "model": result["model"],
        }


    @bp.post("/api/ai/generate-video")
    def ai_generate_video():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or settings_store["supplier"]).strip().lower()
        visual_prompt = str(payload.get("visualPrompt") or "").strip()
        narration_script = str(payload.get("narrationScript") or "")
        aspect_ratio = str(payload.get("aspectRatio") or "9:16").strip()
        start_image_base64 = payload.get("startImageBase64")
        voice_traits = str(payload.get("voiceTraits") or "")
        prebuilt_voice = str(payload.get("prebuiltVoice") or "Zephyr")
        speed = str(payload.get("speed") or "natural")
        sentiment = str(payload.get("sentiment") or "neutral")
        video_to_extend = payload.get("videoToExtend")
        seconds = str(payload.get("seconds") or "8")
        explicit_model = str(payload.get("model") or "").strip()
        video_overrides = _model_overrides_snapshot().get(supplier, {})
        model = (
            explicit_model
            or _resolve_current_model("VIDEO_GEN", supplier)
        )
        if (
            supplier == "google"
            and not explicit_model
            and "VIDEO_GEN" not in video_overrides
            and not str(model or "").startswith("veo-")
        ):
            model = "veo-3.1-generate-preview"
        job_id = uuid4().hex

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        render_jobs_store.create(
            job_id=job_id,
            supplier=supplier,
            prompt=visual_prompt,
            model=model,
            status="running",
        )

        try:
            result = build_ai_runtime(
                profile_registry,
                usage_recorder=resolved_usage_recorder,
            ).generate_video_for_provider(
                operation="generate_video",
                provider=supplier,
                visual_prompt=visual_prompt,
                narration_script=narration_script,
                aspect_ratio=aspect_ratio,
                start_image_base64=start_image_base64,
                voice_traits=voice_traits,
                prebuilt_voice=prebuilt_voice,
                speed=speed,
                sentiment=sentiment,
                video_to_extend=video_to_extend,
                seconds=seconds,
                model=model,
            )
        except VisionDirectorAIProfileError as exc:
            render_jobs_store.mark_error(job_id=job_id, error=str(exc))
            return {"error": str(exc), "jobId": job_id}, 503
        except VisionDirectorAIExecutionError as exc:
            render_jobs_store.mark_error(job_id=job_id, error=str(exc))
            return {"error": str(exc), "jobId": job_id}, 502

        render_jobs_store.mark_success(
            job_id=job_id,
            video_url=result.video_url,
            video_ref=result.video_ref,
        )

        return {
            "url": result.video_url,
            "videoRef": result.video_ref,
            "supplier": result.provider,
            "model": result.model,
            "jobId": job_id,
        }


    @bp.get("/api/usage/report")
    def usage_report():
        return resolved_usage_recorder.report()


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
            "config": resolved_config,
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
        tokens = _admin_tokens()
        next_url = _safe_admin_next_url(request.values.get("next"))

        if not tokens:
            return Response(
                "VisionDirector admin login is unavailable because SMX_VISIONDIRECTOR_ADMIN_TOKEN is not configured.",
                status=503,
                mimetype="text/plain",
            )

        if request.method == "POST":
            submitted = str(request.form.get("token") or "").strip()
            if any(hmac.compare_digest(submitted, token) for token in tokens):
                response = make_response(redirect(next_url))
                response.set_cookie(
                    ADMIN_COOKIE_NAME,
                    submitted,
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

def setup_visiondirector(
    app,
    *,
    project_root: str | Path | None = None,
    init_schema: bool = True,
    ai_profile: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    usage_recorder: UsageRecorder | None = None,
    storage: VisionDirectorStorage | None = None,
    url_prefix: str = DEFAULT_URL_PREFIX,
    **_: Any,
):
    scaffold = ensure_visiondirector_scaffold(project_root=project_root)
    env_config = _config_from_env_file(scaffold.env_file)
    resolved_config = {**env_config, **(config or {})}

    resolved_storage = storage
    if resolved_storage is None:
        resolved_storage = build_storage_from_database_url(
            str(resolved_config.get("SMX_VISIONDIRECTOR_DATABASE_URL") or ""),
            fallback_sqlite_path=scaffold.data_dir / "smx_visiondirector_dev.db",
        )

    if init_schema:
        resolved_storage.initialize()

    resolved_usage_recorder = usage_recorder or SQLiteUsageRecorder(resolved_storage)

    blueprint = create_visiondirector_blueprint(
        config=resolved_config,
        project_root=project_root or PROJECT_ROOT,
        ai_profile=ai_profile,
        usage_recorder=resolved_usage_recorder,
        storage=resolved_storage,
    )
    app.register_blueprint(blueprint, url_prefix=url_prefix)
    return blueprint


def init_visiondirector(
    app,
    *,
    config: dict[str, Any] | None = None,
    project_root: str | Path | None = None,
    init_schema: bool = False,
    ai_profile: dict[str, Any] | None = None,
    usage_recorder: UsageRecorder | None = None,
    storage: VisionDirectorStorage | None = None,
    url_prefix: str = DEFAULT_URL_PREFIX,
    **_: Any,
):
    if storage is not None and init_schema:
        storage.initialize()

    blueprint = create_visiondirector_blueprint(
        config=config,
        project_root=project_root or PROJECT_ROOT,
        ai_profile=ai_profile,
        usage_recorder=usage_recorder,
        storage=storage,
    )
    app.register_blueprint(blueprint, url_prefix=url_prefix)
    return app
