import type { AspectRatio, ParsedScript, Sentiment, SpeechSpeed, VoiceProfile } from "../types";
import type { ModelMapping } from "../types";
import { ensureModelRegistryLoaded, getEffectiveModel, getModelOverride } from "./modelOverrides";


export const OPENAI_MODEL_DEFAULTS = {
  TEXT_MODEL: "gpt-5.1-mini",
  IMAGE_MODEL: "gpt-image-1",
  TRANSCRIBE_MODEL: "gpt-4o-mini-transcribe",
  TTS_MODEL: "gpt-4o-mini-tts",
  VIDEO_MODEL: "sora-2",
} as const;

type OpenAIModelKey = keyof typeof OPENAI_MODEL_DEFAULTS;

function openaiModel(key: OpenAIModelKey): string {
  const override = getModelOverride("openai", String(key));
  if (override) return override;

  const envMap: Record<OpenAIModelKey, any> = {
    TEXT_MODEL: (process as any)?.env?.OPENAI_TEXT_MODEL,
    IMAGE_MODEL: (process as any)?.env?.OPENAI_IMAGE_MODEL,
    TRANSCRIBE_MODEL: (process as any)?.env?.OPENAI_TRANSCRIBE_MODEL,
    TTS_MODEL: (process as any)?.env?.OPENAI_TTS_MODEL,
    VIDEO_MODEL: (process as any)?.env?.OPENAI_VIDEO_MODEL,
  };

  const envVal = envMap[key];
  if (typeof envVal === "string" && envVal.trim()) return envVal.trim();
  return OPENAI_MODEL_DEFAULTS[key];
}

type VideoJob = {
  id: string;
  status: string;
  progress?: number;
  error?: { message?: string };
};

type VideoResult = { url: string; videoRef?: any };

const OPENAI_BASE = "https://api.openai.com/v1";

type OpenAIAgencyKey =
  | "SCRIPT_PARSER"
  | "DICTATION"
  | "VOICE_ANALYZER"
  | "AUTO_NARRATOR"
  | "IMAGE_GEN"
  | "VIDEO_GEN"
  | "TTS_PREVIEW";

async function requireOpenAIModel(key: OpenAIAgencyKey): Promise<string> {
  await ensureModelRegistryLoaded("openai");
  const model = getEffectiveModel("openai", key);
  if (!model) throw new Error(`MODEL_REGISTRY_MISSING_KEY: ${key}`);
  return model;
}

// Safe, small mappings (tweak later if you want)
const SPEED_TO_MULTIPLIER: Record<SpeechSpeed, number> = {
  slower: 0.75,
  slow: 0.85,
  natural: 1.0,
  fast: 1.1,
  faster: 1.4,
};

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function dataUrlToBytes(dataUrl: string): { mime: string; bytes: Uint8Array } {
  // supports both "data:mime;base64,AAA" and raw base64 "AAA"
  const isDataUrl = dataUrl.startsWith("data:");
  const mime = isDataUrl ? (dataUrl.split(";")[0].replace("data:", "") || "application/octet-stream") : "application/octet-stream";
  const b64 = isDataUrl ? dataUrl.split(",")[1] : dataUrl;

  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return { mime, bytes };
}

function normaliseAudioMime(mime: string): string {
  const m = (mime || "").toLowerCase().trim();
  if (m === "audio/mp3") return "audio/mpeg";
  if (m === "audio/x-m4a") return "audio/mp4";
  if (m === "audio/wave") return "audio/wav";
  return m || "application/octet-stream";
}

function filenameForAudio(mime: string, bytes: Uint8Array): { filename: string; mime: string } {
  let m = normaliseAudioMime(mime);

  // Sniff MP3 (ID3 header)
  const isMp3 = bytes.length > 3 && bytes[0] === 0x49 && bytes[1] === 0x44 && bytes[2] === 0x33;
  if (m === "application/octet-stream" && isMp3) m = "audio/mpeg";

  if (m.includes("mpeg")) return { filename: "audio.mp3", mime: m };
  if (m.includes("wav")) return { filename: "audio.wav", mime: m };
  if (m.includes("mp4")) return { filename: "audio.m4a", mime: m };
  if (m.includes("webm")) return { filename: "audio.webm", mime: m };
  if (m.includes("ogg")) return { filename: "audio.ogg", mime: m };

  // Fallback: treat as MP3 (most common)
  return { filename: "audio.mp3", mime: m === "application/octet-stream" ? "audio/mpeg" : m };
}

function bytesToBase64(bytes: Uint8Array): string {
  // chunked to avoid stack blow-ups
  let s = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    s += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(s);
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  return bytesToBase64(new Uint8Array(buf));
}

function aspectToImageSize(ar: AspectRatio): "1024x1024" | "1536x1024" | "1024x1536" {
  if (ar === "16:9") return "1536x1024";
  if (ar === "9:16") return "1024x1536";
  return "1024x1024";
}

function aspectToVideoSize(ar: AspectRatio): "1280x720" | "720x1280" {
  if (ar === "16:9") return "1280x720";
  // Treat 9:16 and 1:1 as portrait for Sora standard sizing.
  return "720x1280";
}


function parseSize(size: string): { w: number; h: number } {
  const [w, h] = size.split("x").map((n) => parseInt(n, 10));
  return { w: Number.isFinite(w) ? w : 720, h: Number.isFinite(h) ? h : 1280 };
}

async function resizeImageDataUrlToPngBlob(dataUrl: string, targetW: number, targetH: number): Promise<Blob> {
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.src = dataUrl;

  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("REFERENCE_IMAGE_LOAD_FAILED"));
  });

  const canvas = document.createElement("canvas");
  canvas.width = targetW;
  canvas.height = targetH;

  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("CANVAS_CONTEXT_FAILED");

  // “Cover” crop: fill target size without letterboxing
  const scale = Math.max(targetW / img.width, targetH / img.height);
  const drawW = img.width * scale;
  const drawH = img.height * scale;
  const dx = (targetW - drawW) / 2;
  const dy = (targetH - drawH) / 2;

  ctx.drawImage(img, dx, dy, drawW, drawH);

  const blob: Blob = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("CANVAS_TO_BLOB_FAILED"))), "image/png");
  });

  return blob;
}

function mapVoiceToOpenAIVoice(v: VoiceProfile): string {
  // Pick from built-in voices
  switch (v) {
    case "Zephyr": return "alloy";
    case "Kore": return "verse";
    case "Puck": return "echo";
    case "Charon": return "onyx";
    case "Fenrir": return "fable";
    case "Aoide": return "nova";
    case "Orion": return "shimmer";

    // Extra presets
    case "Leda": return "ash";
    case "Orus": return "sage";
    case "Umbriel": return "ballad";
    case "Algieba": return "coral";
    case "Enceladus": return "shimmer";

    default: return "alloy";
  }
}

function extractJsonTextFromResponses(respJson: any): string {
  // Prefer output_text if present.
  if (typeof respJson?.output_text === "string" && respJson.output_text.trim()) {
    return respJson.output_text.trim();
  }

  // Otherwise scan output items safely.
  const out = respJson?.output;
  if (!Array.isArray(out)) return "";

  for (const item of out) {
    const content = item?.content;
    if (!Array.isArray(content)) continue;

    for (const c of content) {
      // Various shapes appear across SDKs/REST
      if (typeof c?.text === "string" && c.text.trim()) return c.text.trim();
      if (typeof c?.output_text === "string" && c.output_text.trim()) return c.output_text.trim();
    }
  }

  return "";
}

export class OpenAIService {
  private static getKey(): string {
    const manual = localStorage.getItem("vision_openai_api_key_override");
    if (manual && manual.trim().length > 10) return manual.trim();
    const envKey = (process?.env?.OPENAI_API_KEY || "").trim();
    return envKey;
  }

  private static headersJson(): HeadersInit {
    const key = OpenAIService.getKey();
    if (!key) throw new Error("OPENAI_API_KEY_MISSING");
    return {
      "Authorization": `Bearer ${key}`,
      "Content-Type": "application/json",
    };
  }

  static async parseScript(prompt: string): Promise<ParsedScript> {
    const model = await requireOpenAIModel("SCRIPT_PARSER");

    const body = {
      model,
      instructions:
        "Extract a clean VISUALS prompt and a NARRATION script. " +
        "Return JSON only, matching the schema exactly. If narration is not provided, return narration as an empty string.",
      input: [
        {
          role: "user",
          content: [{ type: "input_text", text: prompt || "" }],
        },
      ],
      text: {
        format: {
          type: "json_schema",
          name: "visiondirector_script",
          strict: true,
          schema: {
            type: "object",
            additionalProperties: false,
            required: ["visuals", "narration"],
            properties: {
              visuals: { type: "string" },
              narration: { type: "string" },
            },
          },
        },
      },
    };

    const res = await fetch(`${OPENAI_BASE}/responses`, {
      method: "POST",
      headers: OpenAIService.headersJson(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const t = await res.text();
      throw new Error(`OPENAI_PARSE_SCRIPT_FAILED: ${t}`);
    }

    const json = await res.json();
    const txt = extractJsonTextFromResponses(json);

    try {
      const parsed = JSON.parse(txt);
      return {
        visuals: String(parsed?.visuals ?? prompt ?? ""),
        narration: String(parsed?.narration ?? ""),
      };
    } catch {
      // Fallback: don’t brick the app
      return { visuals: prompt || "", narration: "" };
    }
  }

  static async generateImage(prompt: string, aspectRatio: AspectRatio): Promise<string | null> {
    const model = await requireOpenAIModel("IMAGE_GEN");
    const size = aspectToImageSize(aspectRatio);

    const body = {
        model,
        prompt: prompt || "",
        size,
        n: 1,
        // For GPT Image models, use output_format (response_format is for DALL·E models).
        output_format: "png",
        quality: "auto",
        background: "auto",
    };

    const res = await fetch(`${OPENAI_BASE}/images/generations`, {
      method: "POST",
      headers: OpenAIService.headersJson(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const t = await res.text();
      throw new Error(`OPENAI_IMAGE_FAILED: ${t}`);
    }

    const json = await res.json();
    const b64 = json?.data?.[0]?.b64_json;
    if (!b64) return null;

    return `data:image/png;base64,${b64}`;
  }

  static async transcribeAudio(audioDataUrl: string): Promise<string> {
    const model = await requireOpenAIModel("DICTATION");

    const key = OpenAIService.getKey();
    if (!key) throw new Error("OPENAI_API_KEY_MISSING");

    // Turn the data: URL into an actual Blob (avoids Uint8Array/bytes.buffer issues entirely)
    const blob0 = await (await fetch(audioDataUrl)).blob();

    // Normalise MIME (OpenAI is picky when mp3 comes through as audio/mp3)
    let mime = (blob0.type || "").toLowerCase().trim();
    if (mime === "audio/mp3") mime = "audio/mpeg";
    if (!mime) mime = "audio/mpeg";

    // Pick a filename that matches the MIME
    let filename = "audio.mp3";
    if (mime.includes("wav")) filename = "audio.wav";
    else if (mime.includes("mp4")) filename = "audio.m4a";
    else if (mime.includes("webm")) filename = "audio.webm";
    else if (mime.includes("ogg")) filename = "audio.ogg";

    // Force the blob to carry the normalised MIME
    const blob = blob0.slice(0, blob0.size, mime);

    const form = new FormData();
    form.append("model", model);
    form.append("file", blob, filename);

    const res = await fetch(`${OPENAI_BASE}/audio/transcriptions`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${key}` },
        body: form,
    });

    if (!res.ok) {
        const t = await res.text();
        throw new Error(`OPENAI_TRANSCRIBE_FAILED: ${t}`);
    }

    const json = await res.json();
    return String(json?.text ?? "").trim();
  }

  static async analyzeVoice(audioBase64: string, sentiment: Sentiment = "neutral"): Promise<string> {
    // This is NOT true “voice cloning”; it’s a text-based style summary to keep the app flowing.
    const transcript = await OpenAIService.transcribeAudio(audioBase64);
    const model = await requireOpenAIModel("VOICE_ANALYZER");

    const body = {
      model,
      instructions:
        "Given the transcript and the target sentiment, produce a short voice-style descriptor " +
        "that a TTS/video model could follow. Return plain text only.",
      input: `Sentiment: ${sentiment}\nTranscript:\n${transcript}`,
    };

    const res = await fetch(`${OPENAI_BASE}/responses`, {
      method: "POST",
      headers: OpenAIService.headersJson(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const t = await res.text();
      throw new Error(`OPENAI_ANALYSE_VOICE_FAILED: ${t}`);
    }

    const json = await res.json();
    const txt = extractJsonTextFromResponses(json);
    return (txt || "Clear, natural delivery.").trim();
  }

  static async playVoicePreview(
    voice: VoiceProfile,
    speed: SpeechSpeed = "natural",
    traits: string = "",
    text: string = "Identity verified."
  ): Promise<void> {
    const ttsModel = await requireOpenAIModel("TTS_PREVIEW");
    const openaiVoice = mapVoiceToOpenAIVoice(voice);
    const rate = SPEED_TO_MULTIPLIER[speed] ?? 1.0;

    const body = {
      model: ttsModel,
      voice: openaiVoice,
      input: `${traits ? `Style notes: ${traits}\n` : ""}${text}`,
      response_format: "wav",
      speed: rate,
    };

    const res = await fetch(`${OPENAI_BASE}/audio/speech`, {
      method: "POST",
      headers: OpenAIService.headersJson(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const t = await res.text();
      throw new Error(`OPENAI_TTS_FAILED: ${t}`);
    }

    const buf = await res.arrayBuffer();
    const blob = new Blob([buf], { type: "audio/wav" });
    const url = URL.createObjectURL(blob);

    // Simple playback
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    await audio.play();
  }

  static async generateVideo(
    visualPrompt: string,
    narrationScript: string,
    aspectRatio: AspectRatio = "9:16",
    startImageBase64?: string,
    voiceTraits?: string,
    prebuiltVoice?: VoiceProfile,
    speed?: SpeechSpeed,
    sentiment?: Sentiment,
    videoToExtend?: any
  ): Promise<VideoResult | null> {
    const key = OpenAIService.getKey();
    if (!key) throw new Error("OPENAI_API_KEY_MISSING");

    const model = await requireOpenAIModel("VIDEO_GEN");
    const size = aspectToVideoSize(aspectRatio);
    const seconds = "12"; // allowed: 4, 8, 12

    const composedPrompt =
      `${visualPrompt || ""}\n\n` +
      `Narration / voiceover:\n${narrationScript || ""}\n\n` +
      `Voice: ${(prebuiltVoice || "alloy")}\n` +
      `Speed: ${(speed || "natural")}\n` +
      `Sentiment: ${(sentiment || "neutral")}\n` +
      (voiceTraits ? `Style traits:\n${voiceTraits}\n` : "");

    // EXTEND mode: remix an existing completed video
    if (videoToExtend && typeof videoToExtend === "string") {
      const remixRes = await fetch(`${OPENAI_BASE}/videos/${videoToExtend}/remix`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${key}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: composedPrompt }),
      });

      if (!remixRes.ok) {
        const t = await remixRes.text();
        throw new Error(`OPENAI_VIDEO_REMIX_FAILED: ${t}`);
      }

      const remixJob: VideoJob = await remixRes.json();
      const done = await OpenAIService.waitForVideo(remixJob.id);
      const dataUrl = await OpenAIService.fetchVideoAsDataUrl(done.id, key);
      return { url: dataUrl, videoRef: done.id };
    }

    // CREATE video job
    const form = new FormData();
    form.append("model", model);
    form.append("prompt", composedPrompt);
    form.append("seconds", seconds);
    form.append("size", size);

    if (startImageBase64) {
        const { w, h } = parseSize(size); // size is your video size string like "720x1280"
        const refBlob = await resizeImageDataUrlToPngBlob(startImageBase64, w, h);
        form.append("input_reference", refBlob, "ref.png");
    }

    const createRes = await fetch(`${OPENAI_BASE}/videos`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${key}` },
      body: form,
    });

    if (!createRes.ok) {
      const t = await createRes.text();
      throw new Error(`OPENAI_VIDEO_CREATE_FAILED: ${t}`);
    }

    const job: VideoJob = await createRes.json();
    const done = await OpenAIService.waitForVideo(job.id);
    const dataUrl = await OpenAIService.fetchVideoAsDataUrl(done.id, key);
    return { url: dataUrl, videoRef: done.id };
  }

  private static async waitForVideo(videoId: string): Promise<VideoJob> {
    const key = OpenAIService.getKey();
    if (!key) throw new Error("OPENAI_API_KEY_MISSING");

    // Poll until completed (keep it bounded)
    for (let i = 0; i < 90; i++) {
      const res = await fetch(`${OPENAI_BASE}/videos/${videoId}`, {
        method: "GET",
        headers: { "Authorization": `Bearer ${key}` },
      });

      if (!res.ok) {
        const t = await res.text();
        throw new Error(`OPENAI_VIDEO_STATUS_FAILED: ${t}`);
      }

      const job: VideoJob = await res.json();

      if (job.status === "completed") return job;
      if (job.status === "failed") {
        throw new Error(job?.error?.message || "OPENAI_VIDEO_FAILED");
      }

      await sleep(1500);
    }

    throw new Error("OPENAI_VIDEO_TIMEOUT");
  }

  private static async fetchVideoAsDataUrl(videoId: string, key: string): Promise<string> {
    const res = await fetch(`${OPENAI_BASE}/videos/${videoId}/content`, {
        method: "GET",
        headers: { "Authorization": `Bearer ${key}` },
    });

    if (!res.ok) {
        const t = await res.text();
        throw new Error(`OPENAI_VIDEO_CONTENT_FAILED: ${t}`);
    }

    const buf = await res.arrayBuffer();
    const blob = new Blob([buf], { type: "video/mp4" });

    // IMPORTANT: blob URL is tiny and won’t nuke localStorage / memory like base64 does
    return URL.createObjectURL(blob);
  }

    static getModelMap(): ModelMapping[] {
        const script = getEffectiveModel("openai", "SCRIPT_PARSER") || "(not loaded)";
        const dictation = getEffectiveModel("openai", "DICTATION") || "(not loaded)";
        const voice = getEffectiveModel("openai", "VOICE_ANALYZER") || "(not loaded)";
        const image = getEffectiveModel("openai", "IMAGE_GEN") || "(not loaded)";
        const tts = getEffectiveModel("openai", "TTS_PREVIEW") || "(not loaded)";
        const video = getEffectiveModel("openai", "VIDEO_GEN") || "(not loaded)";

        return [
            { feature: "Script Intelligence", model: script, role: "Prompt → structured script", context: "Parses user prompts into structured visuals and narration.", file: "services/openaiService.ts", method: "parseScript()  // @MODEL_CALL_SITE" },
            { feature: "Sonic Transcription", model: dictation, role: "Audio → text", context: "Transcribes an uploaded audio track into narration text.", file: "services/openaiService.ts", method: "transcribeAudio()  // @MODEL_CALL_SITE" },
            { feature: "Acoustic DNA Analysis", model: voice, role: "Voice traits inference", context: "Extracts voice traits from a DNA audio reference.", file: "services/openaiService.ts", method: "analyzeVoice()  // @MODEL_CALL_SITE" },
            { feature: "Visual Synthesis", model: image, role: "Text → image", context: "Generates a reference image (when no user image is provided).", file: "services/openaiService.ts", method: "generateImage()  // @MODEL_CALL_SITE" },
            { feature: "Voice Preview", model: tts, role: "Text → speech", context: "Plays a short TTS preview for the selected voice.", file: "services/openaiService.ts", method: "playVoicePreview()  // @MODEL_CALL_SITE" },
            { feature: "Cinematic Video Generation", model: video, role: "Image/text → video", context: "Creates or extends a short clip from the prompt + narration.", file: "services/openaiService.ts", method: "generateVideo()  // @MODEL_CALL_SITE" },
        ];
    }
}
