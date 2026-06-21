from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

module_helpers = r'''
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
'''

if "def _script_parser_prompt(prompt: str) -> str:" not in content:
    content = content.replace(
        "def create_visiondirector_blueprint(",
        module_helpers + "\n" + "def create_visiondirector_blueprint(",
        1,
    )
    print("Inserted module helpers.")

start = content.find("    def _rewrite_runtime_js_urls(js: str) -> str:")
end = content.find("\n    def _rewrite_index_asset_urls", start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate _rewrite_runtime_js_urls block.")
content = content[:start] + '''    def _rewrite_runtime_js_urls(js: str) -> str:
        rewritten = (
            js.replace('\\"/api/', '\\"/visiondirector/api/')
            .replace("'/api/", "'/visiondirector/api/")
            .replace("`/api/", "`/visiondirector/api/")
        )

        if "__smxVisionDirectorParseScript" not in rewritten:
            rewritten = f"{rewritten}\\n{_visiondirector_runtime_js_patch()}\\n"

        return rewritten

''' + content[end:].lstrip("\n")
print("Restored full runtime JS bridge.")

start = content.find("    def _inject_safe_runtime(html: str, *, config, profile_registry) -> str:")
end = content.find("\n    def _visiondirector_index_asset_path", start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate _inject_safe_runtime block.")
content = content[:start] + '''    def _inject_safe_runtime(
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

        return html.replace("<head>", f"<head>\\n  {script}", 1)

''' + content[end:].lstrip("\n")
print("Restored safe runtime injection.")

if "    def home():" not in content:
    idx = content.find('    @bp.get("/index.js")\n')
    if idx < 0:
        raise SystemExit("Could not find /index.js route anchor.")

    home_block = '''    @bp.get("/assets/<path:filename>")
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


'''
    content = content[:idx] + home_block + content[idx:]
    print("Restored public home/assets routes.")

if '"local-visiondirector-admin-token",' not in content:
    content = content.replace(
        '            "local-dev-admin-token",\n',
        '            "local-dev-admin-token",\n            "local-visiondirector-admin-token",\n',
        1,
    )
    print("Restored local admin token fallback.")

if '            "config": resolved_config,' not in content:
    marker = '        payload = {\n'
    idx = content.find(marker, content.find("def _render_admin_dashboard_compatible"))
    if idx < 0:
        raise SystemExit("Could not find admin payload anchor.")
    content = content[:idx + len(marker)] + '            "config": resolved_config,\n' + content[idx + len(marker):]
    print("Restored admin config payload.")

old_model = '''        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("VIDEO_GEN", supplier)
        )
        job_id = uuid4().hex
'''
new_model = '''        explicit_model = str(payload.get("model") or "").strip()
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
'''
if old_model in content:
    content = content.replace(old_model, new_model, 1)
    print("Restored Google video default model behavior.")

setup_start = content.find("\ndef setup_visiondirector")
if setup_start < 0:
    raise SystemExit("Could not find setup_visiondirector tail.")

content = content[:setup_start] + r'''
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
'''
print("Restored setup/init compatibility.")

init_file.write_text(content, encoding="utf-8")
print("Repair complete.")
