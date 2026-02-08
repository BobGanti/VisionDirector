// Minimal type shims so the project can be edited without installing Node/React typings.
// Runtime imports are provided via <script type="importmap"> in index.html.

declare module 'react';
declare module 'react-dom/client';
declare module 'react/jsx-runtime';
declare module '@google/genai';

// If you keep vite.config.ts around, these two avoid editor red squiggles.
declare module 'vite';
declare module '@vitejs/plugin-react';
declare module 'path';

// Browser-side process.env shim (injected by server.js / app.py)
declare const process: {
  env: {
    API_KEY?: string;
    GEMINI_API_KEY?: string;

    // OpenAI
    OPENAI_API_KEY?: string;

    // Optional overrides (if you ever want them later)
    OPENAI_TEXT_MODEL?: string;
    OPENAI_IMAGE_MODEL?: string;
    OPENAI_TTS_MODEL?: string;
    OPENAI_TRANSCRIBE_MODEL?: string;
    OPENAI_VIDEO_MODEL?: string;
  };
};
