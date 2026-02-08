import type { AspectRatio, ParsedScript, Sentiment, SpeechSpeed, VoiceProfile } from "../types";

type VideoJob = {
  id: string;
  status: string;
  progress?: number;
  error?: { message?: string };
};

type VideoResult = { url: string; videoRef?: any };

const OPENAI_BASE = "https://api.openai.com/v1";

// Safe, small mappings (tweak later if you want)
const SPEED_TO_MULTIPLIER: Record<SpeechSpeed, number> = {
  slower: 0.85,
  slow: 0.95,
  natural: 1.0,
  fast: 1.1,
  faster: 1.2,
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

function aspectToVideoSize(ar: AspectRatio): "1280x720" | "720x1280" | "1080x1080" | "1920x1080" | "1024x1792" | "1792x1024" {
  // Keep it compatible with the Video API examples (portrait/landscape).
  if (ar === "16:9") return "1280x720";
  if (ar === "9:16") return "720x1280";
  // Video API doesn’t advertise true 1:1 in the basic examples, so use 1080x1080.
  return "1080x1080";
}

function mapVoiceToOpenAIVoice(v: VoiceProfile): string {
  // Pick from built-in voices (alloy/echo/fable/onyx/nova/verse etc.)
  switch (v) {
    case "Zephyr": return "alloy";
    case "Kore": return "verse";
    case "Puck": return "echo";
    case "Charon": return "onyx";
    case "Fenrir": return "fable";
    case "Aoide": return "nova";
    case "Orion": return "shimmer";
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
    const model = (process?.env?.OPENAI_TEXT_MODEL || "gpt-4o-mini").trim();

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
    const model = (process?.env?.OPENAI_IMAGE_MODEL || "gpt-image-1.5").trim();
    const size = aspectToImageSize(aspectRatio);

    const body = {
      model,
      prompt: prompt || "",
      size,
      n: 1,
      response_format: "b64_json",
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

  static async transcribeAudio(audioBase64: string): Promise<string> {
    const model = (process?.env?.OPENAI_TRANSCRIBE_MODEL || "gpt-4o-mini-transcribe").trim();

    const { mime, bytes } = dataUrlToBytes(audioBase64);
    const blob = new Blob([bytes], { type: mime || "audio/wav" });

    const form = new FormData();
    form.append("model", model);
    form.append("file", blob, "audio.wav");

    const key = OpenAIService.getKey();
    if (!key) throw new Error("OPENAI_API_KEY_MISSING");

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
    const model = (process?.env?.OPENAI_TEXT_MODEL || "gpt-4o-mini").trim();

    const body = {
      model,
      instructions:
        "Given the transcript and the target sentiment, produce a short voice-style descriptor " +
        "that a TTS/video model could follow. Return plain text only.",
      input: [
        {
          role: "user",
          content: [
            { type: "input_text", text: `Sentiment: ${sentiment}\nTranscript:\n${transcript}` },
          ],
        },
      ],
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
    const ttsModel = (process?.env?.OPENAI_TTS_MODEL || "gpt-4o-mini-tts").trim();
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

    const model = (process?.env?.OPENAI_VIDEO_MODEL || "sora-2").trim();
    const size = aspectToVideoSize(aspectRatio);
    const seconds = "4"; // allowed: 4, 8, 12

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
      const { mime, bytes } = dataUrlToBytes(startImageBase64);
      const blob = new Blob([bytes], { type: mime || "image/png" });
      form.append("input_reference", blob, "ref.png");
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
    const b64 = arrayBufferToBase64(buf);
    return `data:video/mp4;base64,${b64}`;
  }
}
