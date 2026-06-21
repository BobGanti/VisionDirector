from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

# Remove any extra bridge-append call from the failed repair attempt.
content = content.replace("            js = _append_runtime_backend_bridges(js)\n", "")

bridge_js = """
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
""".strip()

start = content.find("    def _rewrite_runtime_js_urls(js: str) -> str:")
if start < 0:
    raise SystemExit("Could not find scoped _rewrite_runtime_js_urls function.")

end_candidates = [
    content.find("\n    def _rewrite_index_asset_urls", start),
    content.find("\n    def _visiondirector_index_asset_path", start),
    content.find("\n    def _host_provider_status_payload", start),
]
end_candidates = [pos for pos in end_candidates if pos > start]
if not end_candidates:
    raise SystemExit("Could not find end of _rewrite_runtime_js_urls function.")

end = min(end_candidates)

new_func = f'''    def _rewrite_runtime_js_urls(js: str) -> str:
        replacements = {{
            '\\\"/api/': '\\\"/visiondirector/api/',
            "'/api/": "'/visiondirector/api/",
            "`/api/": "`/visiondirector/api/",
            '\\\"api/': '\\\"/visiondirector/api/',
            "'api/": "'/visiondirector/api/",
            "`api/": "`/visiondirector/api/",
        }}

        rewritten = js
        for old, new in replacements.items():
            rewritten = rewritten.replace(old, new)

        if "__smxVisionDirectorGenerateVideo" not in rewritten or "__smxVisionDirectorProviderVoicePreview" not in rewritten:
            runtime_patch = globals().get("_visiondirector_runtime_js_patch")
            bridge = runtime_patch() if callable(runtime_patch) else {bridge_js!r}
            rewritten = rewritten.rstrip() + "\\n" + bridge + "\\n"

        return rewritten

'''

content = content[:start] + new_func + content[end:].lstrip("\n")
init_file.write_text(content, encoding="utf-8")
print("Repaired _rewrite_runtime_js_urls to append backend bridges safely.")
