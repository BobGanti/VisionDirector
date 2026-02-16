
import { GoogleGenAI, GenerateContentResponse, Modality, Type } from "@google/genai";
import { VoiceProfile, AspectRatio, ParsedScript, ModelMapping, SpeechSpeed, Sentiment } from "../types";
import { decode, decodeAudioData } from "../utils/audioUtils";
import { getModelOverride } from "./modelOverrides";
import { getRuntimeKey } from "./runtimeKeys";

export const MODEL_REGISTRY = {
  SCRIPT_PARSER: 'gemini-3-flash-preview',
  VOICE_ANALYZER: 'gemini-3-flash-preview',
  DICTATION: 'gemini-3-flash-preview',
  AUTO_NARRATOR: 'gemini-3-flash-preview',
  IMAGE_GEN: 'gemini-2.5-flash-image',
  VIDEO_GEN: 'veo-3.1-generate-preview',
  TTS_PREVIEW: 'gemini-2.5-flash-preview-tts'
};

type GeminiModelKey = keyof typeof MODEL_REGISTRY;

function googleModel(key: GeminiModelKey): string {
  return getModelOverride("google", String(key)) || MODEL_REGISTRY[key];
}

function extractInlineData(input: string, fallbackMime: string): { data: string; mimeType: string } {
  const s = String(input || "").trim();

  // data:<mime>;base64,<data>
  if (s.startsWith("data:") && s.includes(";base64,")) {
    const mimeTypeRaw = s.slice(5, s.indexOf(";base64,")) || fallbackMime;
    const data = s.split(",")[1] || "";

    const m = mimeTypeRaw.toLowerCase().trim();
    const normalised =
      m === "audio/mp3" ? "audio/mpeg" :
      m === "audio/x-m4a" ? "audio/mp4" :
      m === "audio/wave" ? "audio/wav" :
      m;

    return { data, mimeType: normalised || fallbackMime };
  }

  // raw base64
  const data = s.includes("base64,") ? s.split("base64,")[1] : s;
  return { data, mimeType: fallbackMime };
}


export class GeminiService {
  private static getAI() {
    const apiKey = getRuntimeKey("google");
    if (!apiKey || apiKey.length < 5) {
      throw new Error("MISSING_API_KEY: Please add your Google key in API Interface Credentials.");
    }
    return new GoogleGenAI({ apiKey });
  }

  static getModelMap(): ModelMapping[] {
    return [
      { feature: "Script Intelligence", model: googleModel("SCRIPT_PARSER"), role: "JSON Extraction", context: "Parses user prompts into structured scenes.", file: "services/geminiService.ts", method: "parseScript()" },
      { feature: "Sonic Transcription", model: googleModel("DICTATION"), role: "Audio-to-Text", context: "Converts voice recordings into text script.", file: "services/geminiService.ts", method: "transcribeAudio()" },
      { feature: "Acoustic DNA Analysis", model: googleModel("VOICE_ANALYZER"), role: "Vocal Signature Extraction", context: "Clones vocal DNA (timbre, resonance, cadence).", file: "services/geminiService.ts", method: "analyzeVoice()" },
      { feature: "Visual Synthesis", model: googleModel("IMAGE_GEN"), role: "T2I / I2I Rendering", context: "Generates the cinematic keyframe.", file: "services/geminiService.ts", method: "generateImage()" },
      { feature: "Cinematic Rendering", model: googleModel("VIDEO_GEN"), role: "Temporal Motion Synthesis", context: "The VEO video generation engine.", file: "services/geminiService.ts", method: "generateVideo()" },
      { feature: "Temporal Consistency", model: "N/A", role: "Prompt Logic", context: "Strict character and lighting stability directives.", file: "services/geminiService.ts", method: "wrapConsistencyPrompt()" }
    ];
  }

  private static wrapConsistencyPrompt(basePrompt: string): string {
    return `[TEMPORAL CONSISTENCY RIGOROUS] ${basePrompt}. Maintain 100% identical character features, clothing textures, and environment lighting throughout the entire sequence. Ensure zero jitter and stable background objects. The sequence must look like a perfectly stitched high-budget film shot.`;
  }

  static async analyzeVoice(audioBase64: string, overrideSentiment?: Sentiment): Promise<string> {
    const ai = this.getAI();
    const { data, mimeType } = extractInlineData(audioBase64, "audio/wav");
    
    const response = await ai.models.generateContent({
      model: googleModel("VOICE_ANALYZER"),
      contents: { 
        parts: [
          { inlineData: { data, mimeType } }, 
          { text: `ACT AS A VOCAL FORENSIC ANALYST. Extract the exact acoustic signature for high-fidelity voice cloning. 
          Identify: 
          1. Timbre & Resonance (raspiness, airiness, depth).
          2. Micro-Accent & Dialect markers.
          3. Emotional Baseline & Cadence (rhythm, word stress, pauses).
          4. Age & Vocal Weight.
          Output a single descriptive 'Acoustic Signature' paragraph that a voice synthesis engine can use to reproduce this EXACT voice with 99% resemblance.` }
        ] 
      }
    });
    return response.text?.trim() || "Natural human voice";
  }

  static async generateVideo(
    visualPrompt: string,
    narrationScript: string,
    aspectRatio: AspectRatio = "16:9",
    startImageBase64?: string,
    voiceTraits?: string,
    prebuiltVoice?: VoiceProfile,
    speed: SpeechSpeed = "natural",
    sentiment: Sentiment = "neutral",
    videoToExtend?: any,
    seconds: "4" | "8" | "12" = "8"
  ): Promise<{ url: string; videoRef: any } | null> {

    const ai = this.getAI();

    if (seconds !== "8") {
      console.warn("[VisionDirector] Google video duration is fixed to 8s. Ignoring seconds=", seconds);
    }
    
    const cleanStart = startImageBase64?.includes('base64,') ? startImageBase64.split('base64,')[1] : startImageBase64;
    
    const sentimentMap: Record<Sentiment, string> = {
      neutral: "natural",
      cinematic: "dramatic",
      aggressive: "loud and tense",
      whispering: "very quiet and intimate",
      joyful: "cheerful",
      somber: "melancholic"
    };

    const cleanText = (s?: string, maxLen: number = 1400) => {
      if (!s) return "";
      // Prevent nested quotes / broken instruction blocks
      let t = String(s)
        .replace(/\r\n/g, "\n")
        .replace(/\r/g, "\n")
        .replace(/"/g, "'")
        .replace(/\u0000/g, "")
        .trim();

      // Collapse whitespace
      t = t.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();

      if (t.length > maxLen) t = t.slice(0, maxLen).trim();
      return t;
    };

    const cleanNarration = cleanText(narrationScript, 1600);
    const cleanTraits = cleanText(voiceTraits || "", 1200);

    const base = String(prebuiltVoice || "Zephyr");

    const voiceBlock = cleanTraits
      ? `[VOICE_PROFILE]\nbase_voice: ${base}\n\n[VOICE_RESEMBLANCE_DNA]\n${cleanTraits}`
      : `[VOICE_PROFILE]\nbase_voice: ${base}`;

    const audioBlock = cleanNarration
      ? [
          `[AUDIO DIRECTIVES - HIGHEST PRIORITY]`,
          `- The narration MUST match the speaker in the voice block below (accent, pitch range, cadence).`,
          `- Do NOT drift to a generic voice, even if the narration contains punctuation or quotes.`,
          `- Read the narration text verbatim. Do not paraphrase or add extra words.`,
          ``,
          `[DELIVERY]`,
          `style: ${sentimentMap[sentiment]}`,
          `speed: ${speed}`,
          ``,
          voiceBlock,
          ``,
          `[NARRATION_TEXT - READ VERBATIM]`,
          cleanNarration
        ].join("\n")
      : `Ambient cinematic audio with zero narration.`;

    // Keep temporal consistency rules focused on visuals, then append audio directives.
    const visualOnly = this.wrapConsistencyPrompt(visualPrompt || "Cinematic sequence");
    const finalPrompt = `${visualOnly}\n\n${audioBlock}`;


    let operation;
    if (videoToExtend) {
      operation = await ai.models.generateVideos({
        model: googleModel("VIDEO_GEN"),
        prompt: `[DIRECTOR_EXTENSION_REQUEST]\n${finalPrompt}\n\n[EXTENSION]\nThis is a continuation of the previous clip. Ensure identical vocal timbre and identical visual subjects.`,
        video: videoToExtend,
        config: { 
          numberOfVideos: 1, 
          resolution: '720p', 
          aspectRatio: (aspectRatio === '9:16' ? '9:16' : '16:9')
        }
      });
    } else {
      operation = await ai.models.generateVideos({
        model: googleModel("VIDEO_GEN"),
        prompt: finalPrompt, 
        image: cleanStart ? { imageBytes: cleanStart, mimeType: 'image/png' } : undefined,
        config: { 
          numberOfVideos: 1, 
          resolution: '720p', 
          aspectRatio: (aspectRatio === '9:16' ? '9:16' : '16:9')
        }
      });
    }

    while (!operation.done) {
      await new Promise(r => setTimeout(r, 8000));
      operation = await ai.operations.getVideosOperation({ operation });
    }

    if (operation.error) throw new Error(operation.error.message);

    const videoObj = operation.response?.generatedVideos?.[0]?.video;
    const uri = videoObj?.uri;
    if (!uri) throw new Error("Output stream empty.");
    
    const apiKey = getRuntimeKey("google");
    if (!apiKey) throw new Error("MISSING_API_KEY: Please add your Google key in API Interface Credentials.");
    const res = await fetch(`${uri}&key=${encodeURIComponent(apiKey)}`);

    const b = await res.blob();
    return { url: URL.createObjectURL(b), videoRef: videoObj };
  }

  static async playVoicePreview(
    voice: VoiceProfile,
    speed: SpeechSpeed = 'natural',
    traits: string = "",
    text: string = "Identity verified."
  ): Promise<void> {
    const ai = this.getAI();

    const response = await ai.models.generateContent({
      model: googleModel("TTS_PREVIEW"),
      contents: [{ parts: [{ text: `Profile: ${traits}. Style: ${speed}. Script: ${text}` }] }],
      config: {
        responseModalities: [Modality.AUDIO],
        speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: (voice as any) } } }
      }
    });

    const data = response.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
    if (!data) throw new Error("PREVIEW_FAILED: No audio returned.");

    const AudioCtx = (window.AudioContext || (window as any).webkitAudioContext) as any;
    const ctx = new AudioCtx({ sampleRate: 24000 }) as AudioContext;

    // Browsers may start the context suspended until a user gesture occurs.
    if (ctx.state === 'suspended') await ctx.resume();

    const buffer = await decodeAudioData(decode(data), ctx, 24000, 1);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start();
  }

  static async parseScript(prompt: string): Promise<ParsedScript> {
    if (!prompt.trim()) return { visuals: "", narration: "" };
    const ai = this.getAI();
    const response = await ai.models.generateContent({
      model: googleModel("SCRIPT_PARSER"),
      contents: prompt,
      config: {
        systemInstruction: "JSON output only. Split input into 'visuals' (camera/scene in []) and 'narration' (speech). If no visuals, create cinematic camera work. Ensure character names are consistent.",
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: { visuals: { type: Type.STRING }, narration: { type: Type.STRING } },
          required: ["visuals", "narration"]
        }
      }
    });
    return JSON.parse(response.text) as ParsedScript;
  }

  static async transcribeAudio(audioBase64: string): Promise<string> {
    const ai = this.getAI();
    const { data, mimeType } = extractInlineData(audioBase64, "audio/wav");
    const response = await ai.models.generateContent({
      model: googleModel("DICTATION"),
     contents: { parts: [{ inlineData: { data, mimeType } }, { text: "Transcribe audio exactly." }] }
    });
    return response.text?.trim() || "";
  }

  static async generateImage(prompt: string, aspectRatio: AspectRatio = "9:16"): Promise<string | null> {
    const ai = this.getAI();
    const response = await ai.models.generateContent({
      model: googleModel("IMAGE_GEN"),
      contents: { parts: [{ text: `High-fidelity cinematic production keyframe: ${prompt}. Photo-realistic lighting.` }] },
      config: { imageConfig: { aspectRatio: aspectRatio as any } }
    });
    const part = response.candidates?.[0]?.content?.parts.find(p => p.inlineData);
    return part ? `data:image/png;base64,${part.inlineData.data}` : null;
  }
}
