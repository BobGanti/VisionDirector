from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_provider_backed_voice_preview.py")

content = runtime_file.read_text(encoding="utf-8")

if "GOOGLE_TTS_PREVIEW_MODEL" not in content:
    insert_after = "# smx-visiondirector provider-backed TTS preview bindings\n"
    idx = content.find(insert_after)
    if idx < 0:
        raise SystemExit("Could not find provider-backed TTS preview bindings marker.")

    constants = dedent(
        '''
        GOOGLE_TTS_PREVIEW_MODEL = "gemini-3.1-flash-tts-preview"


        def _smx_is_google_tts_model(model: str | None) -> bool:
            return "tts" in str(model or "").strip().lower()


        def _smx_resolve_google_tts_model(model: str | None) -> str:
            if _smx_is_google_tts_model(model):
                return str(model).strip()
            return GOOGLE_TTS_PREVIEW_MODEL


        '''
    )

    content = content[: idx + len(insert_after)] + constants + content[idx + len(insert_after):]
    print("added Google TTS preview model guard")
else:
    print("Google TTS preview model guard already present")

old = '''                if profile.provider == "google":
                    audio_url = _smx_google_voice_preview(
                        profile,
                        model=selected_model,
                        voice=voice,
                        speed=speed,
                        traits=traits,
                        text=text,
                    )
'''

new = '''                if profile.provider == "google":
                    selected_model = _smx_resolve_google_tts_model(selected_model)
                    audio_url = _smx_google_voice_preview(
                        profile,
                        model=selected_model,
                        voice=voice,
                        speed=speed,
                        traits=traits,
                        text=text,
                    )
'''

if old not in content:
    raise SystemExit("Could not find Google voice preview branch to patch.")

content = content.replace(old, new, 1)
runtime_file.write_text(content, encoding="utf-8")
print("patched Google voice preview to force a TTS-capable model")


test_content = test_file.read_text(encoding="utf-8")

if "test_google_voice_preview_does_not_use_text_only_host_model" not in test_content:
    test_content += dedent(
        r'''


        def test_google_voice_preview_does_not_use_text_only_host_model(tmp_path):
            fake = FakeGoogleClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {
                        "provider": "google",
                        "model": "gemini-2.5-flash",
                        "client": fake,
                    }
                },
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/preview-voice",
                json={
                    "supplier": "google",
                    "voice": "Puck",
                    "speed": "natural",
                    "traits": "warm delivery",
                    "text": "Puck",
                },
            )

            assert response.status_code == 200
            assert fake.models.calls
            assert fake.models.calls[-1]["model"] == "gemini-3.1-flash-tts-preview"
            assert response.get_json()["model"] == "gemini-3.1-flash-tts-preview"
        '''
    )

    test_file.write_text(test_content, encoding="utf-8")
    print("added Google TTS model guard regression test")
else:
    print("Google TTS model guard regression test already present")
