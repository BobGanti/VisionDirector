
import { GoogleGenAI, GenerateContentResponse, Modality, Type } from "@google/genai";
import { VoiceProfile, AspectRatio, ParsedScript, ModelMapping, SpeechSpeed, Sentiment } from "../types";
import { decode, decodeAudioData } from "../utils/audioUtils";
import { getModelOverride } from "./modelOverrides";

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

export class GeminiService {
  private static getAI() {
    const manualKey = localStorage.getItem('vision_api_key_override');
    const envKey = process.env.API_KEY;
    const apiKey = manualKey || (envKey !== "undefined" ? envKey : null);
    
    if (!apiKey || apiKey.length < 5) {
      throw new Error("MISSING_API_KEY: Please set your API key in the Secure Vault (Architectural Map).");
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

  // const textModel = getEffectiveModel("openai", "SCRIPT_PARSER") || "(registry not loaded)";
  // const imageModel = getEffectiveModel("openai", "IMAGE_GEN") || "(registry not loaded)";
  // const transcribeModel = getEffectiveModel("openai", "DICTATION") || "(registry not loaded)";
  // const ttsModel = getEffectiveModel("openai", "TTS_PREVIEW") || "(registry not loaded)";
  // const videoModel = getEffectiveModel("openai", "VIDEO_GEN") || "(registry not loaded)";


  private static wrapConsistencyPrompt(basePrompt: string): string {
    return `[TEMPORAL CONSISTENCY RIGOROUS] ${basePrompt}. Maintain 100% identical character features, clothing textures, and environment lighting throughout the entire sequence. Ensure zero jitter and stable background objects. The sequence must look like a perfectly stitched high-budget film shot.`;
  }

  static async analyzeVoice(audioBase64: string, overrideSentiment?: Sentiment): Promise<string> {
    const ai = this.getAI();
    const clean = audioBase64.includes('base64,') ? audioBase64.split('base64,')[1] : audioBase64;
    
    const response = await ai.models.generateContent({
      model: googleModel("VOICE_ANALYZER"),
      contents: { 
        parts: [
          { inlineData: { data: clean, mimeType: 'audio/wav' } }, 
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
    speed: SpeechSpeed = 'natural',
    sentiment: Sentiment = 'neutral',
    videoToExtend?: any
  ): Promise<{ url: string, videoRef: any } | null> {
    const ai = this.getAI();
    const cleanStart = startImageBase64?.includes('base64,') ? startImageBase64.split('base64,')[1] : startImageBase64;
    
    const sentimentMap: Record<Sentiment, string> = {
      neutral: "natural", cinematic: "dramatic", aggressive: "loud and tense", whispering: "very quiet and intimate", joyful: "cheerful", somber: "melancholic"
    };

    // HIGH PRIORITY ACOUSTIC BLOCK - Ensures the DNA takes precedence over any prebuilt selection
    const vocalBlock = voiceTraits 
      ? `[VOICE_RESEMBLANCE_DNA: ${voiceTraits}]` 
      : `[VOICE_PROFILE: ${prebuiltVoice}]`;

    const audioContext = narrationScript 
      ? `${vocalBlock} Character Narration: "${narrationScript}". Style: ${sentimentMap[sentiment]}. Delivery Speed: ${speed}. The voice MUST sound EXACTLY like the provided DNA/Signature.` 
      : `Ambient cinematic audio with zero narration.`;
    
    const basePrompt = `${visualPrompt || 'Cinematic sequence'}. ${audioContext}`;
    const finalPrompt = this.wrapConsistencyPrompt(basePrompt);

    let operation;
    if (videoToExtend) {
      operation = await ai.models.generateVideos({
        model: googleModel("VIDEO_GEN"),
        prompt: `[DIRECTOR_EXTENSION_REQUEST] ${finalPrompt}. This is a continuation of the previous clip. Ensure identical vocal timbre and visual subjects.`,
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
    
    const res = await fetch(`${uri}&key=${process.env.API_KEY || localStorage.getItem('vision_api_key_override')}`);
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
    const clean = audioBase64.includes('base64,') ? audioBase64.split('base64,')[1] : audioBase64;
    const response = await ai.models.generateContent({
      model: googleModel("DICTATION"),
      contents: { parts: [{ inlineData: { data: clean, mimeType: 'audio/wav' } }, { text: "Transcribe audio exactly." }] }
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
