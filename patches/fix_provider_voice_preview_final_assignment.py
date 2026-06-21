from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
test_file = Path("tests/test_provider_backed_voice_preview.py")

content = init_file.read_text(encoding="utf-8")

marker = "__smxVisionDirectorProviderVoicePreviewFinalOverride"

if marker in content:
    print("Final provider-backed voice preview override already present.")
else:
    lines = content.splitlines()

    host_warn_idx = None
    for i, line in enumerate(lines):
        if "Failed to install host AI provider patch" in line:
            host_warn_idx = i
            break

    if host_warn_idx is None:
        raise SystemExit("Could not find host AI provider patch warning anchor.")

    insert_idx = None
    for j in range(host_warn_idx + 1, min(host_warn_idx + 8, len(lines))):
        if lines[j].strip() == '"",':
            insert_idx = j + 1
            break

    if insert_idx is None:
        raise SystemExit("Could not find insertion point after host AI provider patch block.")

    js = dedent(
        r'''
        // __smxVisionDirectorProviderVoicePreviewFinalOverride
        try {
          if (typeof __smxVisionDirectorProviderVoicePreview === "function") {
            if (typeof googleProvider !== "undefined") {
              googleProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "google");
            }
            if (typeof openaiProvider !== "undefined") {
              openaiProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "openai");
            }
          }
        } catch (error) {
          console.warn("[smx-visiondirector] Failed to install final provider-backed voice preview patch", error);
        }
        '''
    ).strip("\n")

    entries = ["        " + repr(line) + "," for line in js.splitlines()]
    lines = lines[:insert_idx] + entries + lines[insert_idx:]

    init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Added final provider-backed voice preview override after browser fallback block.")


test_content = test_file.read_text(encoding="utf-8")

if "test_provider_backed_voice_preview_is_final_play_voice_assignment" not in test_content:
    test_content += dedent(
        r'''


        def test_provider_backed_voice_preview_is_final_play_voice_assignment(tmp_path):
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {"provider": "google", "model": "google-main", "client": FakeGoogleClient()},
                    "assistant": {"provider": "openai", "model": "openai-main", "client": FakeOpenAIClient()},
                },
            )

            response = app.test_client().get("/visiondirector/index.js")

            assert response.status_code == 200
            js = response.get_data(as_text=True)

            google_last = js.rfind("googleProvider.playVoicePreview")
            openai_last = js.rfind("openaiProvider.playVoicePreview")

            assert google_last > -1
            assert openai_last > -1

            google_tail = js[google_last : google_last + 300]
            openai_tail = js[openai_last : openai_last + 300]

            assert "__smxVisionDirectorProviderVoicePreview" in google_tail
            assert "__smxVisionDirectorProviderVoicePreview" in openai_tail
            assert "__smxVisionDirectorPlayVoicePreview" not in google_tail
            assert "__smxVisionDirectorPlayVoicePreview" not in openai_tail
        '''
    )

    test_file.write_text(test_content, encoding="utf-8")
    print("Added final-assignment regression test.")
else:
    print("Final-assignment regression test already present.")
