from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
test_file = ROOT / "tests" / "test_voice_preview_runtime_patch.py"

content = init_file.read_text(encoding="utf-8")

helper_name = "__smxVisionDirectorPlayVoicePreview"

if helper_name not in content:
    anchor = "\ntry {\n  if (typeof googleProvider !== \"undefined\") {"
    if anchor not in content:
        raise SystemExit("Could not find host AI patch try-block anchor in __init__.py.")

    helper = dedent(
        r'''
        async function __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, supplier) {
          const phrase = String(text || "Voice preview.");
          const selectedVoice = String(voice || "").trim();
          const selectedSpeed = String(speed || "natural").toLowerCase();

          if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
            throw new Error("BROWSER_TTS_UNAVAILABLE");
          }

          const rateMap = {
            slower: 0.75,
            slow: 0.88,
            natural: 1.0,
            fast: 1.12,
            faster: 1.25
          };

          const utterance = new SpeechSynthesisUtterance(phrase);
          utterance.rate = rateMap[selectedSpeed] || 1.0;
          utterance.pitch = 1.0;
          utterance.volume = 1.0;

          const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
          if (Array.isArray(voices) && voices.length) {
            const target = selectedVoice.toLowerCase();
            const matched = voices.find((v) => String(v.name || "").toLowerCase().includes(target));
            if (matched) {
              utterance.voice = matched;
            }
          }

          window.speechSynthesis.cancel();

          await new Promise((resolve, reject) => {
            utterance.onend = () => resolve();
            utterance.onerror = (event) => reject(new Error(`VOICE_PREVIEW_FAILED: ${event?.error || "unknown"}`));
            window.speechSynthesis.speak(utterance);
          });

          return true;
        }

        '''
    ).rstrip()

    content = content.replace(anchor, "\n" + helper + anchor, 1)
    print("added browser-safe playVoicePreview helper")
else:
    print("playVoicePreview helper already present")


google_anchor = '    googleProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, "google");'
google_insert = google_anchor + '\n    googleProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, "google");'

if google_anchor in content and "googleProvider.playVoicePreview" not in content:
    content = content.replace(google_anchor, google_insert, 1)
    print("added google playVoicePreview override")


openai_anchor = '    openaiProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, "openai");'
openai_insert = openai_anchor + '\n    openaiProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, "openai");'

if openai_anchor in content and "openaiProvider.playVoicePreview" not in content:
    content = content.replace(openai_anchor, openai_insert, 1)
    print("added openai playVoicePreview override")

init_file.write_text(content, encoding="utf-8")


test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        from flask import Flask

        from smx_visiondirector import setup_visiondirector


        def test_runtime_patch_overrides_voice_preview_without_browser_provider_keys(tmp_path):
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {
                        "provider": "google",
                        "model": "host-google-model",
                        "client": object(),
                    }
                },
            )

            response = app.test_client().get("/visiondirector/index.js")

            assert response.status_code == 200
            js = response.get_data(as_text=True)

            assert "__smxVisionDirectorPlayVoicePreview" in js
            assert "googleProvider.playVoicePreview" in js
            assert "openaiProvider.playVoicePreview" in js
            assert "speechSynthesis" in js
            assert "BROWSER_TTS_UNAVAILABLE" in js
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("created tests/test_voice_preview_runtime_patch.py")
