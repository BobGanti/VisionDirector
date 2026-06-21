from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

if "def _append_runtime_backend_bridges(js: str) -> str:" not in content:
    anchor = "    def _visiondirector_index_asset_path(filename: str) -> Path | None:"
    if anchor not in content:
        raise SystemExit("Could not find _visiondirector_index_asset_path anchor.")

    helper = dedent(
        '''
        def _append_runtime_backend_bridges(js: str) -> str:
            if "__smxVisionDirectorGenerateVideo" in js and "__smxVisionDirectorProviderVoicePreview" in js:
                return js

            bridge = """
// __smxVisionDirectorBackendBridge
async function __smxVisionDirectorGenerateVideo(payloadOrSupplier, visualPrompt, narrationScript, aspectRatio, seconds, startImageBase64, videoToExtend) {
  const payload = typeof payloadOrSupplier === "object" && payloadOrSupplier !== null
    ? payloadOrSupplier
    : {
        supplier: payloadOrSupplier,
        visualPrompt: visualPrompt,
        narrationScript: narrationScript,
        aspectRatio: aspectRatio,
        seconds: seconds,
        startImageBase64: startImageBase64,
        videoToExtend: videoToExtend
      };

  const response = await fetch("/visiondirector/api/ai/generate-video", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    throw new Error(data.error || data.message || "VIDEO_GENERATION_FAILED");
  }
  return data;
}

async function __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, supplier) {
  const response = await fetch("/visiondirector/api/ai/preview-voice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      supplier: supplier,
      voice: voice,
      speed: speed,
      traits: traits,
      text: text
    })
  });

  const data = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    throw new Error(data.error || data.message || "VOICE_PREVIEW_FAILED");
  }

  if (data.audioUrl) {
    const audio = new Audio(data.audioUrl);
    await audio.play();
  }

  return data;
}

// __smxVisionDirectorGenerateVideoFinalOverride
try {
  if (typeof googleProvider !== "undefined") {
    googleProvider.generateVideo = function (payloadOrPrompt, narrationScript, aspectRatio, seconds, startImageBase64, videoToExtend) {
      return __smxVisionDirectorGenerateVideo(
        typeof payloadOrPrompt === "object" && payloadOrPrompt !== null
          ? Object.assign({}, payloadOrPrompt, { supplier: "google" })
          : {
              supplier: "google",
              visualPrompt: payloadOrPrompt,
              narrationScript: narrationScript,
              aspectRatio: aspectRatio,
              seconds: seconds,
              startImageBase64: startImageBase64,
              videoToExtend: videoToExtend
            }
      );
    };
  }

  if (typeof openaiProvider !== "undefined") {
    openaiProvider.generateVideo = function (payloadOrPrompt, narrationScript, aspectRatio, seconds, startImageBase64, videoToExtend) {
      return __smxVisionDirectorGenerateVideo(
        typeof payloadOrPrompt === "object" && payloadOrPrompt !== null
          ? Object.assign({}, payloadOrPrompt, { supplier: "openai" })
          : {
              supplier: "openai",
              visualPrompt: payloadOrPrompt,
              narrationScript: narrationScript,
              aspectRatio: aspectRatio,
              seconds: seconds,
              startImageBase64: startImageBase64,
              videoToExtend: videoToExtend
            }
      );
    };
  }
} catch (error) {
  console.warn("VisionDirector video backend bridge was not attached.", error);
}

// __smxVisionDirectorProviderVoicePreviewFinalOverride
try {
  if (typeof googleProvider !== "undefined") {
    googleProvider.playVoicePreview = function (voice, speed, traits, text) {
      return __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "google");
    };
  }

  if (typeof openaiProvider !== "undefined") {
    openaiProvider.playVoicePreview = function (voice, speed, traits, text) {
      return __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "openai");
    };
  }
} catch (error) {
  console.warn("VisionDirector voice preview backend bridge was not attached.", error);
}
"""
            return js.rstrip() + "\\n" + bridge + "\\n"


        '''
    )

    helper = "\n".join(("    " + line) if line.strip() else "" for line in helper.splitlines())
    content = content.replace(anchor, helper + "\n" + anchor, 1)
    print("Inserted _append_runtime_backend_bridges helper.")
else:
    print("_append_runtime_backend_bridges helper already present.")

old = '''            js = selected.read_text(encoding="utf-8")
            js = _rewrite_runtime_js_urls(js)
            return Response(js, mimetype="application/javascript")
'''

new = '''            js = selected.read_text(encoding="utf-8")
            js = _rewrite_runtime_js_urls(js)
            js = _append_runtime_backend_bridges(js)
            return Response(js, mimetype="application/javascript")
'''

if old in content:
    content = content.replace(old, new, 1)
    print("Patched /index.js route to append backend bridges.")
elif "_append_runtime_backend_bridges(js)" in content:
    print("/index.js route already appends backend bridges.")
else:
    raise SystemExit("Could not patch /index.js route bridge append.")

init_file.write_text(content, encoding="utf-8")
print("Runtime backend bridge repair complete.")
