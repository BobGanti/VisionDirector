from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
test_file = ROOT / "tests" / "test_voice_preview_runtime_patch.py"

content = init_file.read_text(encoding="utf-8")


def js_list_entries(js: str) -> list[str]:
    return ["        " + repr(line) + "," for line in js.splitlines()]


if "__smxVisionDirectorPlayVoicePreview" not in content:
    helper_js = dedent(
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
            utterance.onend = () => resolve(true);
            utterance.onerror = (event) => reject(new Error(`VOICE_PREVIEW_FAILED: ${event?.error || "unknown"}`));
            window.speechSynthesis.speak(utterance);
          });

          return true;
        }
        '''
    ).strip("\n")

    anchor = '        "try {",'
    idx = content.find(anchor)
    if idx < 0:
        raise SystemExit('Could not find list-entry anchor: "try {",')

    helper_block = "\n".join(js_list_entries(helper_js)) + "\n"
    content = content[:idx] + helper_block + content[idx:]
    print("added playVoicePreview helper into runtime JS lines list")
else:
    print("playVoicePreview helper already present")


if "googleProvider.playVoicePreview" not in content:
    needle = "googleProvider.generateVideo ="
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if needle in line:
            override_js = '    googleProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, "google");'
            lines.insert(i + 1, "        " + repr(override_js) + ",")
            content = "\n".join(lines) + "\n"
            print("added google playVoicePreview override")
            break
    else:
        raise SystemExit("Could not find googleProvider.generateVideo list entry.")
else:
    print("google playVoicePreview override already present")


if "openaiProvider.playVoicePreview" not in content:
    needle = "openaiProvider.generateVideo ="
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if needle in line:
            override_js = '    openaiProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, "openai");'
            lines.insert(i + 1, "        " + repr(override_js) + ",")
            content = "\n".join(lines) + "\n"
            print("added openai playVoicePreview override")
            break
    else:
        raise SystemExit("Could not find openaiProvider.generateVideo list entry.")
else:
    print("openai playVoicePreview override already present")


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
                    },
                    "assistant": {
                        "provider": "openai",
                        "model": "host-openai-model",
                        "client": object(),
                    },
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
            assert "HOST_PROVIDER_NOT_READY" in js
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("created tests/test_voice_preview_runtime_patch.py")
