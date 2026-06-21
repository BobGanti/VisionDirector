from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_provider_backed_voice_preview.py")

content = runtime_file.read_text(encoding="utf-8")

if 'OPENAI_TTS_PREVIEW_MODEL = "gpt-4o-mini-tts"' not in content:
    if 'GOOGLE_TTS_PREVIEW_MODEL = "gemini-3.1-flash-tts-preview"\n' not in content:
        raise SystemExit("Could not find GOOGLE_TTS_PREVIEW_MODEL anchor.")
    content = content.replace(
        'GOOGLE_TTS_PREVIEW_MODEL = "gemini-3.1-flash-tts-preview"\n',
        'GOOGLE_TTS_PREVIEW_MODEL = "gemini-3.1-flash-tts-preview"\n'
        'OPENAI_TTS_PREVIEW_MODEL = "gpt-4o-mini-tts"\n'
        'OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"\n',
        1,
    )
    print("added OpenAI TTS constants")
else:
    print("OpenAI TTS constants already present")


if "def _smx_resolve_openai_tts_model(" not in content:
    anchor = dedent(
        '''
        def _smx_resolve_google_tts_model(model: str | None) -> str:
            if _smx_is_google_tts_model(model):
                return str(model).strip()
            return GOOGLE_TTS_PREVIEW_MODEL
        '''
    ).strip()

    if anchor not in content:
        raise SystemExit("Could not find _smx_resolve_google_tts_model anchor.")

    insert = anchor + dedent(
        '''


        def _smx_is_openai_tts_model(model: str | None) -> bool:
            value = str(model or "").strip().lower()
            return (
                value == "gpt-4o-mini-tts"
                or value.startswith("gpt-4o-mini-tts-")
                or value in {"tts-1", "tts-1-hd"}
            )


        def _smx_resolve_openai_tts_model(model: str | None) -> str:
            if _smx_is_openai_tts_model(model):
                return str(model).strip()
            return OPENAI_TTS_PREVIEW_MODEL


        def _smx_ensure_openai_client_base_url(client: Any) -> None:
            """
            OpenAI provider profiles should use an absolute OpenAI API base URL.

            Some host/sandbox clients can accidentally carry a relative base URL such
            as "/v1", which later fails as: Invalid URL (POST /v1/audio/speech).
            This does not instantiate a new model/client; it only normalizes the
            host-provided OpenAI client when its base URL is clearly invalid.
            """
            if client is None:
                return

            current = ""
            try:
                current = str(getattr(client, "base_url", "") or "").strip()
            except Exception:
                current = ""

            if current and "://" in current:
                return

            try:
                setattr(client, "base_url", OPENAI_DEFAULT_BASE_URL)
            except Exception:
                pass
        '''
    ).rstrip()

    content = content.replace(anchor, insert, 1)
    print("added OpenAI TTS model/base_url helpers")
else:
    print("OpenAI TTS helpers already present")


old = '''def _smx_openai_voice_preview(
    profile: ProviderProfile,
    *,
    model: str,
    voice: Any,
    speed: str,
    traits: str,
    text: str,
) -> str:
    client = profile.client
    audio = getattr(client, "audio", None)
'''
new = '''def _smx_openai_voice_preview(
    profile: ProviderProfile,
    *,
    model: str,
    voice: Any,
    speed: str,
    traits: str,
    text: str,
) -> str:
    client = profile.client
    _smx_ensure_openai_client_base_url(client)
    audio = getattr(client, "audio", None)
'''

if old in content:
    content = content.replace(old, new, 1)
    print("patched OpenAI voice preview to normalize base_url")
elif "_smx_ensure_openai_client_base_url(client)" in content:
    print("OpenAI voice preview already normalizes base_url")
else:
    raise SystemExit("Could not patch _smx_openai_voice_preview.")


old_branch = '''        elif profile.provider == "openai":
            audio_url = _smx_openai_voice_preview(
                profile,
                model=selected_model,
'''
new_branch = '''        elif profile.provider == "openai":
            selected_model = _smx_resolve_openai_tts_model(selected_model)
            audio_url = _smx_openai_voice_preview(
                profile,
                model=selected_model,
'''

if old_branch in content:
    content = content.replace(old_branch, new_branch, 1)
    print("patched OpenAI voice preview to use TTS model")
elif "selected_model = _smx_resolve_openai_tts_model(selected_model)" in content:
    print("OpenAI voice preview already resolves TTS model")
else:
    raise SystemExit("Could not patch OpenAI branch in preview_voice_for_provider.")

runtime_file.write_text(content, encoding="utf-8")
print("patched ai_runtime.py")


tests = test_file.read_text(encoding="utf-8")

if "test_openai_voice_preview_uses_tts_model_and_repairs_relative_base_url" not in tests:
    tests += dedent(
        '''


        def test_openai_voice_preview_uses_tts_model_and_repairs_relative_base_url(tmp_path):
            fake = FakeOpenAIClient()
            fake.base_url = "/v1"

            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "client": fake,
                    }
                },
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/preview-voice",
                json={
                    "supplier": "openai",
                    "voice": "echo",
                    "speed": "natural",
                    "traits": "clear delivery",
                    "text": "OpenAI preview",
                },
            )

            assert response.status_code == 200
            assert str(fake.base_url) == "https://api.openai.com/v1"
            assert fake.audio.speech.calls
            call = fake.audio.speech.calls[-1]
            assert call["model"] == "gpt-4o-mini-tts"
            assert call["voice"] == "echo"
            assert call["response_format"] == "wav"
            assert response.get_json()["model"] == "gpt-4o-mini-tts"
        '''
    )
    print("added OpenAI voice preview regression test")
else:
    print("OpenAI voice preview regression test already present")

test_file.write_text(tests, encoding="utf-8")
print("patched tests")
