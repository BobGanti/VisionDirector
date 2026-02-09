import type { AspectRatio, ParsedScript, Sentiment, SpeechSpeed, VoiceProfile } from "../types";
import { GeminiService } from "./geminiService";
import { OpenAIService } from "./openaiService";

export type Supplier = "google" | "openai";
export type VideoResult = { url: string; videoRef?: any };

export interface AIProvider {
  parseScript(prompt: string): Promise<ParsedScript>;
  generateImage(prompt: string, aspectRatio: AspectRatio): Promise<string | null>;
  analyzeVoice(audioBase64: string, sentiment?: Sentiment): Promise<string>;
  transcribeAudio(audioBase64: string): Promise<string>;
  playVoicePreview(
    voice: VoiceProfile,
    speed?: SpeechSpeed,
    traits?: string,
    text?: string
  ): Promise<void>;

  generateVideo(
    visualPrompt: string,
    narrationScript: string,
    aspectRatio?: AspectRatio,
    startImageBase64?: string,
    voiceTraits?: string,
    prebuiltVoice?: VoiceProfile,
    speed?: SpeechSpeed,
    sentiment?: Sentiment,
    videoToExtend?: any
  ): Promise<VideoResult | null>;
}

const googleProvider: AIProvider = {
  parseScript: (prompt) => GeminiService.parseScript(prompt),
  generateImage: (prompt, aspectRatio) => GeminiService.generateImage(prompt, aspectRatio),
  analyzeVoice: (audioBase64, sentiment) => GeminiService.analyzeVoice(audioBase64, sentiment),
  transcribeAudio: (audioBase64) => GeminiService.transcribeAudio(audioBase64),
  playVoicePreview: (voice, speed = "natural", traits = "", text = "Identity verified.") =>
    GeminiService.playVoicePreview(voice, speed, traits, text),
  generateVideo: (
    visualPrompt,
    narrationScript,
    aspectRatio,
    startImageBase64,
    voiceTraits,
    prebuiltVoice,
    speed,
    sentiment,
    videoToExtend
  ) =>
    GeminiService.generateVideo(
      visualPrompt,
      narrationScript,
      aspectRatio,
      startImageBase64,
      voiceTraits,
      prebuiltVoice,
      speed,
      sentiment,
      videoToExtend
    ),
};

const openaiProvider: AIProvider = {
  parseScript: (prompt) => OpenAIService.parseScript(prompt),
  generateImage: (prompt, aspectRatio) => OpenAIService.generateImage(prompt, aspectRatio),
  analyzeVoice: (audioBase64, sentiment) => OpenAIService.analyzeVoice(audioBase64, sentiment),
  transcribeAudio: (audioBase64) => OpenAIService.transcribeAudio(audioBase64),
  playVoicePreview: (voice, speed = "natural", traits = "", text = "Identity verified.") =>
    OpenAIService.playVoicePreview(voice, speed, traits, text),
  generateVideo: async (
    visualPrompt,
    narrationScript,
    aspectRatio,
    startImageBase64,
    voiceTraits,
    prebuiltVoice,
    speed,
    sentiment,
    videoToExtend
  ) => {
    try {
      return await OpenAIService.generateVideo(
        visualPrompt,
        narrationScript,
        aspectRatio,
        startImageBase64,
        voiceTraits,
        prebuiltVoice,
        speed,
        sentiment,
        videoToExtend
      );
    } catch (e: any) {
      const msg = String(e?.message || e || "");
      const m = msg.toLowerCase();

      const blocked =
        m.includes("blocked") ||
        m.includes("moderation") ||
        m.includes("safety") ||
        m.includes("policy");

      if (!blocked) throw e;

      console.warn("[VisionDirector] OpenAI video blocked. Falling back to Google video…");

      try {
        return await GeminiService.generateVideo(
          visualPrompt,
          narrationScript,
          aspectRatio,
          startImageBase64,
          voiceTraits,
          prebuiltVoice,
          speed,
          sentiment,
          videoToExtend
        );
      } catch (g: any) {
        const gmsg = String(g?.message || g || "");
        throw new Error(
          `OPENAI_VIDEO_BLOCKED: OpenAI refused this video request. ` +
          `Set a Google API key (or switch Supplier to GOOGLE) to render video. ` +
          `OpenAI: ${msg} | Google fallback: ${gmsg}`
        );
      }
    }
  },

};

export function getAIProvider(supplier: Supplier): AIProvider {
  return supplier === "openai" ? openaiProvider : googleProvider;
}
