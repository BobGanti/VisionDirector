from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_ai_generate_video_route.py")

content = runtime_file.read_text(encoding="utf-8")

if 'OPENAI_VIDEO_DEFAULT_MODEL = "sora-2"' not in content:
    anchor = 'OPENAI_TTS_PREVIEW_MODEL = "gpt-4o-mini-tts"\n'
    if anchor not in content:
        raise SystemExit("Could not find OPENAI_TTS_PREVIEW_MODEL anchor.")
    content = content.replace(
        anchor,
        anchor + 'OPENAI_VIDEO_DEFAULT_MODEL = "sora-2"\n',
        1,
    )
    print("added OpenAI video default model")
else:
    print("OpenAI video default model already present")


if "def _smx_resolve_openai_video_model(" not in content:
    helpers = dedent(
        '''


        def _smx_is_openai_video_model(model: str | None) -> bool:
            value = str(model or "").strip().lower()
            return value in {
                "sora-2",
                "sora-2-pro",
                "sora-2-2025-10-06",
                "sora-2-pro-2025-10-06",
                "sora-2-2025-12-08",
            }


        def _smx_resolve_openai_video_model(model: str | None) -> str:
            if _smx_is_openai_video_model(model):
                return str(model).strip()
            return OPENAI_VIDEO_DEFAULT_MODEL


        def _smx_openai_input_reference(start_image_base64: str | None) -> dict[str, str] | None:
            raw = str(start_image_base64 or "").strip()
            if not raw:
                return None

            if raw.startswith("http://") or raw.startswith("https://"):
                return {"image_url": raw}

            if raw.startswith("data:image/"):
                return {"image_url": raw}

            if "base64," in raw:
                return {"image_url": raw}

            return {"image_url": "data:image/png;base64," + raw}
        '''
    ).rstrip()

    content = content.rstrip() + helpers + "\n"
    print("added OpenAI video model/reference helpers")
else:
    print("OpenAI video helpers already present")


old_branch = '''            elif profile.provider == "openai":
                provider_result = _generate_openai_video(
                    profile,
                    prompt=prompt,
                    model=selected_model,
'''
new_branch = '''            elif profile.provider == "openai":
                selected_model = _smx_resolve_openai_video_model(selected_model)
                provider_result = _generate_openai_video(
                    profile,
                    prompt=prompt,
                    model=selected_model,
'''

if old_branch in content:
    content = content.replace(old_branch, new_branch, 1)
    print("patched OpenAI video branch to use Sora model resolver")
elif "selected_model = _smx_resolve_openai_video_model(selected_model)" in content:
    print("OpenAI video branch already resolves Sora model")
else:
    raise SystemExit("Could not patch OpenAI branch in generate_video_for_provider.")


old_start = '''def _generate_openai_video(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
    start_image_base64: str | None,
    video_to_extend: Any,
    seconds: str,
) -> _ProviderVideoResponse:
    client = profile.client
    videos = getattr(client, "videos", None)
'''
new_start = '''def _generate_openai_video(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
    start_image_base64: str | None,
    video_to_extend: Any,
    seconds: str,
) -> _ProviderVideoResponse:
    client = profile.client
    _smx_ensure_openai_client_base_url(client)
    videos = getattr(client, "videos", None)
'''

if old_start in content:
    content = content.replace(old_start, new_start, 1)
    print("patched OpenAI video to normalize base_url")
elif "_smx_ensure_openai_client_base_url(client)\n    videos = getattr(client, \"videos\", None)" in content:
    print("OpenAI video already normalizes base_url")
else:
    raise SystemExit("Could not patch _generate_openai_video start.")


old_reference = '''        ref_bytes = _decode_data_url_bytes(start_image_base64)
        if ref_bytes:
            kwargs["input_reference"] = ref_bytes
'''
new_reference = '''        input_reference = _smx_openai_input_reference(start_image_base64)
        if input_reference:
            kwargs["input_reference"] = input_reference
'''

if old_reference in content:
    content = content.replace(old_reference, new_reference, 1)
    print("patched OpenAI input_reference shape")
elif "_smx_openai_input_reference(start_image_base64)" in content:
    print("OpenAI input_reference already patched")
else:
    raise SystemExit("Could not patch OpenAI input_reference block.")

runtime_file.write_text(content, encoding="utf-8")
print("patched ai_runtime.py")


tests = test_file.read_text(encoding="utf-8")

tests = tests.replace(
    'json={"overrides": {"VIDEO_GEN": "current-openai-video-model"}}',
    'json={"overrides": {"VIDEO_GEN": "sora-2-pro"}}',
)
tests = tests.replace(
    'assert payload["model"] == "current-openai-video-model"',
    'assert payload["model"] == "sora-2-pro"',
)
tests = tests.replace(
    'assert openai.videos.calls[-1]["model"] == "current-openai-video-model"',
    'assert openai.videos.calls[-1]["model"] == "sora-2-pro"',
)

if "self.base_url = \"/v1\"" not in tests:
    tests = tests.replace(
        "class FakeOpenAIClient:\n"
        "    def __init__(self):\n"
        "        self.videos = FakeOpenAIVideos()\n",
        "class FakeOpenAIClient:\n"
        "    def __init__(self):\n"
        "        self.base_url = \"/v1\"\n"
        "        self.videos = FakeOpenAIVideos()\n",
        1,
    )

if "test_generate_video_route_falls_back_to_sora_when_host_openai_profile_is_text_model" not in tests:
    tests += dedent(
        '''


        def test_generate_video_route_falls_back_to_sora_when_host_openai_profile_is_text_model(tmp_path):
            openai = FakeOpenAIClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "api_key": "SECRET_OPENAI",
                        "client": openai,
                    }
                },
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "openai",
                    "visualPrompt": "A cinematic village compound",
                    "narrationScript": "A father speaks to his son.",
                    "aspectRatio": "9:16",
                    "seconds": "12",
                },
            )

            assert response.status_code == 200
            payload = response.get_json()

            assert payload["supplier"] == "openai"
            assert payload["model"] == "sora-2"
            assert openai.videos.calls[-1]["model"] == "sora-2"
            assert openai.videos.calls[-1]["seconds"] == "12"
            assert str(openai.base_url) == "https://api.openai.com/v1"


        def test_generate_video_route_sends_openai_start_image_as_input_reference(tmp_path):
            openai = FakeOpenAIClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "client": openai,
                    }
                },
            )

            start_image = "data:image/png;base64,AAAA"
            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "openai",
                    "visualPrompt": "Continue from the portrait frame",
                    "aspectRatio": "9:16",
                    "seconds": "8",
                    "startImageBase64": start_image,
                },
            )

            assert response.status_code == 200
            assert openai.videos.calls[-1]["input_reference"] == {"image_url": start_image}
        '''
    )

test_file.write_text(tests, encoding="utf-8")
print("patched OpenAI video tests")
