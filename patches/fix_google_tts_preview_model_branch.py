from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_provider_backed_voice_preview.py")

content = runtime_file.read_text(encoding="utf-8")
lines = content.splitlines()

start = None
for i, line in enumerate(lines):
    if line.strip().startswith("def _smx_preview_voice_for_provider("):
        start = i
        break

if start is None:
    raise SystemExit("Could not find _smx_preview_voice_for_provider.")

end = None
for j in range(start + 1, len(lines)):
    if "VisionDirectorAIRuntime.preview_voice_for_provider" in lines[j]:
        end = j
        break

if end is None:
    raise SystemExit("Could not find preview_voice_for_provider binding end.")

google_if = None
for k in range(start, end):
    if lines[k].strip() == 'if profile.provider == "google":':
        google_if = k
        break

if google_if is None:
    raise SystemExit("Could not find Google branch inside _smx_preview_voice_for_provider.")

nearby = "\n".join(lines[google_if: min(google_if + 8, len(lines))])
if "_smx_resolve_google_tts_model(selected_model)" in nearby:
    print("Google TTS model branch is already guarded.")
else:
    indent = lines[google_if][: len(lines[google_if]) - len(lines[google_if].lstrip())] + "    "
    lines.insert(google_if + 1, f"{indent}selected_model = _smx_resolve_google_tts_model(selected_model)")
    runtime_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Inserted Google TTS-capable model guard into preview branch.")


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
    print("Added Google TTS model guard regression test.")
else:
    print("Google TTS model guard regression test already present.")
