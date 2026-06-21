from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

start = content.find("    def _rewrite_runtime_js_urls(js: str) -> str:")
if start < 0:
    raise SystemExit("Could not find _rewrite_runtime_js_urls.")

end = content.find("\n    def _rewrite_index_asset_urls", start)
if end < 0:
    raise SystemExit("Could not find _rewrite_index_asset_urls after _rewrite_runtime_js_urls.")

new_func = dedent(
    r'''
    def _rewrite_runtime_js_urls(js: str) -> str:
        """
        Serve the browser bundle from the plugin namespace and append the
        provider-backed runtime bridges expected by the SyntaxMatrix host.
        """
        replacements = {
            '"/api/': '"/visiondirector/api/',
            "'/api/": "'/visiondirector/api/",
            "`/api/": "`/visiondirector/api/",
            '"api/': '"/visiondirector/api/',
            "'api/": "'/visiondirector/api/",
            "`api/": "`/visiondirector/api/",
        }

        patched = js
        for old, new in replacements.items():
            patched = patched.replace(old, new)

        if "__smxVisionDirectorGenerateVideo" in patched and "__smxVisionDirectorProviderVoicePreview" in patched:
            return patched

        bridge = r'''

// __smxVisionDirectorBackendBridge
async function __smxVisionDirectorGenerateVideo(payloadOrSupplier, visualPrompt, narrationScript, aspectRatio, seconds, startImageBase64, videoToExtend) {
  const payload = typeof payloadOrSupplier === "object" && payloadOrSupplier !== null
    ? payloadOrSupplier
    : {
        supplier: payloadOrSupplier,
        visualPrompt,
        narrationScript,
        aspectRatio,
        seconds,
        startImageBase64,
        videoToExtend
      };

  const response = await fetch("/visiondirector/api/ai/generate-video", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await response.json().catch(() => ({}));
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
      supplier,
      voice,
      speed,
      traits,
      text
    })
  });

  const data = await response.json().catch(() => ({}));
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
    googleProvider.generateVideo = (payloadOrPrompt, narrationScript, aspectRatio, seconds, startImageBase64, videoToExtend) =>
      __smxVisionDirectorGenerateVideo(
        typeof payloadOrPrompt === "object" && payloadOrPrompt !== null
          ? { ...payloadOrPrompt, supplier: "google" }
          : {
              supplier: "google",
              visualPrompt: payloadOrPrompt,
              narrationScript,
              aspectRatio,
              seconds,
              startImageBase64,
              videoToExtend
            }
      );
  }

  if (typeof openaiProvider !== "undefined") {
    openaiProvider.generateVideo = (payloadOrPrompt, narrationScript, aspectRatio, seconds, startImageBase64, videoToExtend) =>
      __smxVisionDirectorGenerateVideo(
        typeof payloadOrPrompt === "object" && payloadOrPrompt !== null
          ? { ...payloadOrPrompt, supplier: "openai" }
          : {
              supplier: "openai",
              visualPrompt: payloadOrPrompt,
              narrationScript,
              aspectRatio,
              seconds,
              startImageBase64,
              videoToExtend
            }
      );
  }
} catch (error) {
  console.warn("VisionDirector video backend bridge was not attached.", error);
}

// __smxVisionDirectorProviderVoicePreviewFinalOverride
try {
  if (typeof googleProvider !== "undefined") {
    googleProvider.playVoicePreview = (voice, speed, traits, text) =>
      __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "google");
  }

  if (typeof openaiProvider !== "undefined") {
    openaiProvider.playVoicePreview = (voice, speed, traits, text) =>
      __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "openai");
  }
} catch (error) {
  console.warn("VisionDirector voice preview backend bridge was not attached.", error);
}
'''
        return patched.rstrip() + "\n" + bridge + "\n"
    '''
).rstrip()

new_func = "\n".join(("    " + line) if line.strip() else "" for line in new_func.splitlines())

content = content[:start] + new_func + "\n" + content[end:]
init_file.write_text(content, encoding="utf-8")
print("Restored runtime JS backend bridges.")
