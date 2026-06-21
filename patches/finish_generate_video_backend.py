from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not init_file.exists():
    raise SystemExit("Run from VisionDirector root.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


init = init_file.read_text(encoding="utf-8")

if '@bp.post("/api/ai/generate-video")' not in init:
    marker = '    @bp.get("/api/usage/report")\n'
    if marker not in init:
        raise SystemExit("Could not find usage report marker for route insertion.")

    route = '''    @bp.post("/api/ai/generate-video")
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

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

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
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "url": result.video_url,
            "videoRef": result.video_ref,
            "supplier": result.provider,
            "model": result.model,
        }


'''
    init = init.replace(marker, route + marker, 1)
    print("inserted generate-video route")
else:
    print("generate-video route already present")

if "__smxVisionDirectorGenerateVideo" not in init:
    old = '''        "  return data?.imageDataUrl || null;",
        "}",
        "",
        "try {",
'''
    new = '''        "  return data?.imageDataUrl || null;",
        "}",
        "",
        "async function __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, supplier) {",
        '  const res = await fetch("/visiondirector/api/ai/generate-video", {',
        '    method: "POST",',
        '    headers: { "Content-Type": "application/json" },',
        "    body: JSON.stringify({",
        "      supplier,",
        "      visualPrompt,",
        "      narrationScript,",
        "      aspectRatio,",
        "      startImageBase64,",
        "      voiceTraits,",
        "      prebuiltVoice,",
        "      speed,",
        "      sentiment,",
        "      videoToExtend,",
        "      seconds",
        "    })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) {",
        "    throw new Error(data?.error || `VISIONDIRECTOR_GENERATE_VIDEO_FAILED: ${res.status}`);",
        "  }",
        "  return { url: data?.url || \\"\\", videoRef: data?.videoRef || null };",
        "}",
        "",
        "try {",
'''
    if old not in init:
        raise SystemExit("Could not find runtime image helper list block.")
    init = init.replace(old, new, 1)
    print("inserted runtime JS generate-video helper")
else:
    print("runtime JS generate-video helper already present")

google_line = '''        '    googleProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "google");',
'''
google_video_line = '''        '    googleProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, "google");',
'''

if google_video_line not in init:
    if google_line not in init:
        raise SystemExit("Could not find google generateImage provider patch line.")
    init = init.replace(google_line, google_line + google_video_line, 1)
    print("patched googleProvider.generateVideo")
else:
    print("googleProvider.generateVideo already patched")

openai_line = '''        '    openaiProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "openai");',
'''
openai_video_line = '''        '    openaiProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, "openai");',
'''

if openai_video_line not in init:
    if openai_line not in init:
        raise SystemExit("Could not find openai generateImage provider patch line.")
    init = init.replace(openai_line, openai_line + openai_video_line, 1)
    print("patched openaiProvider.generateVideo")
else:
    print("openaiProvider.generateVideo already patched")

init_file.write_text(init, encoding="utf-8")

write_file(
    "tests/test_ai_generate_video_route.py",
    """
    from __future__ import annotations

    import base64

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeGoogleModels:
        def __init__(self):
            self.calls = []

        def generate_videos(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "done": True,
                "response": {
                    "generatedVideos": [
                        {
                            "video": {
                                "uri": "data:video/mp4;base64,GOOGLE_VIDEO_B64",
                                "name": "google-video-1",
                            }
                        }
                    ]
                },
            }


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    class FakeOpenAIVideos:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return {"id": "openai-video-1", "status": "completed"}

        def content(self, video_id):
            assert video_id == "openai-video-1"
            return b"OPENAI_VIDEO_BYTES"


    class FakeOpenAIClient:
        def __init__(self):
            self.videos = FakeOpenAIVideos()


    def test_generate_video_route_uses_host_google_profile_and_video_model(tmp_path):
        google = FakeGoogleClient()
        app = Flask(__name__)
        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "host-google-fallback",
                    "api_key": "SECRET_GOOGLE",
                    "client": google,
                }
            },
        )

        client = app.test_client()
        override = client.post(
            "/visiondirector/api/model-overrides/google",
            json={"overrides": {"VIDEO_GEN": "current-google-video-model"}},
        )
        assert override.status_code == 200

        response = client.post(
            "/visiondirector/api/ai/generate-video",
            json={
                "supplier": "google",
                "visualPrompt": "A cinematic tower",
                "narrationScript": "Welcome home.",
                "aspectRatio": "16:9",
                "seconds": "8",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["supplier"] == "google"
        assert payload["model"] == "current-google-video-model"
        assert payload["url"] == "data:video/mp4;base64,GOOGLE_VIDEO_B64"
        assert google.models.calls[-1]["model"] == "current-google-video-model"
        assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


    def test_generate_video_route_uses_host_openai_profile_and_returns_data_url(tmp_path):
        openai = FakeOpenAIClient()
        app = Flask(__name__)
        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "assistant": {
                    "provider": "openai",
                    "model": "host-openai-fallback",
                    "api_key": "SECRET_OPENAI",
                    "client": openai,
                }
            },
        )

        client = app.test_client()
        override = client.post(
            "/visiondirector/api/model-overrides/openai",
            json={"overrides": {"VIDEO_GEN": "current-openai-video-model"}},
        )
        assert override.status_code == 200

        response = client.post(
            "/visiondirector/api/ai/generate-video",
            json={
                "supplier": "openai",
                "visualPrompt": "A cinematic tower",
                "narrationScript": "Welcome home.",
                "aspectRatio": "9:16",
                "seconds": "8",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()

        expected_b64 = base64.b64encode(b"OPENAI_VIDEO_BYTES").decode("ascii")
        assert payload["supplier"] == "openai"
        assert payload["model"] == "current-openai-video-model"
        assert payload["url"] == f"data:video/mp4;base64,{expected_b64}"
        assert openai.videos.calls[-1]["model"] == "current-openai-video-model"
        assert "SECRET_OPENAI" not in response.get_data(as_text=True)


    def test_runtime_js_patches_video_generation_to_backend(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path)

        response = app.test_client().get("/visiondirector/index.js")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "__smxVisionDirectorGenerateVideo" in body
        assert "/visiondirector/api/ai/generate-video" in body
        assert "googleProvider.generateVideo =" in body
        assert "openaiProvider.generateVideo =" in body
    """,
)

print("Patch complete: generateVideo route and JS override are installed.")
