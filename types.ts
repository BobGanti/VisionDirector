
export interface MediaAsset {
  id: string;
  type: 'image' | 'video' | 'audio';
  url: string;
  prompt?: string;
  timestamp: number;
  fileName: string;
  videoRef?: any; // Stores the raw API video object for extensions
}

export interface ParsedScript {
  visuals: string;
  narration: string;
}

export type VoiceProfile = 'Zephyr' | 'Kore' | 'Puck' | 'Charon' | 'Fenrir' | 'Aoide' | 'Orion' | string;
export type AspectRatio = '9:16' | '16:9' | '1:1' | '4:3' | '3:4';
export type SpeechSpeed = 'slower' | 'slow' | 'natural' | 'fast' | 'faster';
export type Sentiment = 'neutral' | 'cinematic' | 'aggressive' | 'whispering' | 'joyful' | 'somber';

export interface CustomVoice {
  id: string;
  label: string;
  baseVoice: VoiceProfile;
  traits: string;
  speed: SpeechSpeed;
  sentiment?: Sentiment;
}

export enum AppStatus {
  IDLE = 'IDLE',
  ANALYZING_SCRIPT = 'ANALYZING_SCRIPT',
  GENERATING_IMAGE = 'GENERATING_IMAGE',
  GENERATING_AUDIO = 'GENERATING_AUDIO',
  GENERATING_VIDEO = 'GENERATING_VIDEO',
  EXTENDING_VIDEO = 'EXTENDING_VIDEO',
  ERROR = 'ERROR'
}

export interface ModelMapping {
  feature: string;
  model: string;
  role: string;
  context: string;
  file: string;
  method: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}
