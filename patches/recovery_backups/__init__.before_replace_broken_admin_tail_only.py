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


    @bp.get("/health")
    def health():
        return {
            "status": "ok",
            "package": "smx-visiondirector",
            "has_ai_profile": profile_registry.has_any(),
            "has_main_profile": profile_registry.has_role("main"),
            "has_assistant_profile": profile_registry.has_role("assistant"),
        }


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
        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("VIDEO_GEN", supplier)
        )
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
    def _smx_visiondirector_admin_logout():
        """Log out the VisionDirector admin user by clearing the admin cookie."""
        response = make_response(redirect("/visiondirector/admin/login"))
        response.delete_cookie(
            ADMIN_COOKIE_NAME,
            path=DEFAULT_URL_PREFIX,
        )
        return response

    return bp


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
