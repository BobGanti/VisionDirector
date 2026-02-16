# VisionDirector — Knowledgebase (Text/Image → Video Studio)

VisionDirector is a lightweight studio app for turning **sequence prompts** and **starting media** (images / videos / audio) into short videos, with optional **voice identity capture** and **model routing controls**.

This document is written as a **knowledgebase**: it explains *how to get started*, *how each feature works*, and answers common “what if…” questions.

---

## Contents

- [1) Quick start](#1-quick-start)
- [2) How the app works](#2-how-the-app-works)
- [3) Using the Studio](#3-using-the-studio)
- [4) Asset Vault](#4-asset-vault)
- [5) Supplier switching (Google/OpenAI)](#5-supplier-switching-googleopenai)
- [6) API Interface Credentials (Secure Vault)](#6-api-interface-credentials-secure-vault)
- [7) Model Blueprint (Model Map + overrides)](#7-model-blueprint-model-map--overrides)
- [8) Voice identities](#8-voice-identities)
- [9) Themes and UI scale](#9-themes-and-ui-scale)
- [10) Data storage and security](#10-data-storage-and-security)
- [11) Backend API reference](#11-backend-api-reference)
- [12) Troubleshooting](#12-troubleshooting)
- [13) FAQ](#13-faq)
- [14) Repo structure](#14-repo-structure)
- [15) Questions for you](#15-questions-for-you)

---

## 1) Quick start

### Option A — Run with Python (Flask)

1) Create a virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install flask cryptography gunicorn
```

2) Start the server:

```bash
python app.py
```

3) Open:

- `http://localhost:8080`

> Note: `app.py` serves the compiled frontend and exposes the `/api/*` endpoints (settings, credentials, model overrides, voice identities).

---

### Option B — Run with Node (Express static host)

If you already have `node_modules/` present in your folder, you can run:

```bash
node server.js
```

Open:

- `http://localhost:8080`

> The Express server primarily serves static files and injects environment variables into the page. If you need the `/api/*` endpoints, run the Flask server instead.

---

### Option C — Run in Docker (recommended for deployments)

The repository contains a `Dockerfile` intended to build the UI and run the Python backend with Gunicorn.

Typical usage (example):

```bash
docker build -t visiondirector .
docker run -p 8080:8080 -e PORT=8080 visiondirector
```

For persistent storage, mount a volume and set `DATABASE_PATH`:

```bash
docker run -p 8080:8080 \
  -e PORT=8080 \
  -e DATABASE_PATH=/data/db.sqlite \
  -v $(pwd)/data:/data \
  visiondirector
```

---

## 2) How the app works

VisionDirector has three moving parts:

1) **Studio UI** (React)
   - The main screen where you type a sequence prompt, select supplier, choose aspect ratio, pick voice settings, and render.

2) **Backend API** (Flask blueprint)
   - Stores settings and secrets in SQLite.
   - Exposes endpoints like `/api/settings/supplier`, `/api/credentials/*`, `/api/model-overrides/*`, `/api/voice-identities/*`.

3) **AI provider services** (frontend “provider” layer)
   - `services/geminiService.ts` (Google)
   - `services/openaiService.ts` (OpenAI)
   - `services/aiProvider.ts` chooses the provider based on your **Supplier** selection.

A typical render cycle looks like this:

1) You select a **Supplier** (Google/OpenAI).
2) You enter or generate a **Sequence Narrative** (visuals + narration).
3) You optionally choose an **image** as a starting frame, or a **video** to extend.
4) The provider runs:
   - Script parsing (optional, depending on your flow)
   - Image generation (optional)
   - Voice analysis (optional)
   - Video generation (required)
5) The output video is shown and added to your **Asset Vault**.

---

## 3) Using the Studio

### 3.1 Studio controls (top bar)

You will see:

- **Supplier**: `Google` or `OpenAI`
- **Speed**: voice delivery speed (slower → faster)
- **Sentiment**: narration style (neutral, cinematic, aggressive, whispering, joyful, somber)
- **Aspect**: typically `16:9` (landscape) or `9:16` (portrait)

These affect how your provider builds prompts and requests.

### 3.2 Sequence Narrative (main editor)

This is the primary input box. The recommended structure is:

- **Visual direction**: in brackets, shot-by-shot
- **Narration**: quoted line, or written plainly

Example:

```
[Wide shot] A rain-soaked Dublin street at night. Neon reflections. Slow dolly-in.
[Close-up] The protagonist checks a device, tense but calm.

"Narration: The future isn’t built in a sprint. It’s kept reliable in the long run."
```

If you want **silent** videos, omit narration or set it to an empty line.

### 3.3 Execute Render

- If your selected asset is an **image** (or nothing), `Execute Render` generates a new video.
- If your selected asset is a **video**, the UI switches into **Extension mode**, and the button becomes `Extend Sequence`.

In extension mode:
- Your prompt should describe *what happens next*, continuing the previous clip.
- The provider uses the previous video reference to extend and maintain continuity.

### 3.4 Extension mode (what changes)

Extension mode is detected when the active asset is a video with a `videoRef`.

In this mode the UI:
- Re-labels the prompt area (for continuation)
- Uses the prior clip as `videoToExtend`
- Uses a continuation prompt so the next segment matches the original

---

## 4) Asset Vault

The Asset Vault is your working set of media. It supports:

- **Images**: used as starting frames for image-to-video
- **Videos**: outputs and “extendable” clips
- **Audio**: for dictation and voice analysis (where supported)

### Desktop vs mobile

- On desktop, the Asset Vault is a sidebar.
- On mobile, it appears as a slide-out drawer (opened via the hamburger button).

### Common Vault actions

- **Upload**: add images/audio (and videos if your build supports it)
- **Select**: sets an asset as the “active” one
- **Delete**: removes it from the vault list
- **Use in render**:
  - Active image → used as the starting reference image (if supported by supplier)
  - Active video → enables Extension mode

---

## 5) Supplier switching (Google/OpenAI)

### What “Supplier” means

Supplier controls which provider implementation is used:

- **Google**: Gemini + Veo generation flow (`services/geminiService.ts`)
- **OpenAI**: OpenAI models incl. Sora video (`services/openaiService.ts`)

### Default supplier

The backend endpoint `/api/settings/supplier` provides the default supplier.
If nothing has been saved yet, it returns **google** by default.

### Persistence

When you change supplier, the UI should POST to:

- `POST /api/settings/supplier` with `{ "supplier": "google" | "openai" }`

The value is stored in SQLite:

- Table: `app_settings`
- Key: `supplier`

### OpenAI video fallback

When OpenAI video generation fails for content policy / moderation reasons, the OpenAI provider attempts a fallback to Google video generation (see `services/aiProvider.ts`).

This behaviour is intentional so a single blocked request does not break your workflow.

---

## 6) API Interface Credentials (Secure Vault)

This panel lives inside **Model Blueprint** and is your “keys vault”.

### What it stores

- Google API key (Gemini / Veo)
- OpenAI API key

These are stored in SQLite **encrypted at rest**:

- Table: `api_credentials`
- Encryption: `cryptography.fernet` (see `data/credentials.py`)
- Master key file: `data/syntaxmatrixdir/.vd_master_key`

### Runtime key handling (important)

Keys are:
- stored securely in the database,
- loaded into an **in-memory runtime store** in the frontend (not persistent storage),
- then used by the provider services for API calls.

This is done by:

- `services/runtimeKeys.ts` → `warmRuntimeKeys()` / `refreshRuntimeKey()`
- Endpoint: `GET /api/credentials/<supplier>`

### Delete key

Deleting a key calls:

- `DELETE /api/credentials/<supplier>`

This removes the encrypted entry from SQLite.

### Security notes

- Keys are never displayed back in the UI.
- Keys should not be shipped in source control.
- The master key file must be treated as sensitive.

---

## 7) Model Blueprint (Model Map + overrides)

Model Blueprint is your “wiring console” for model selection.

It provides:
- A live map of each capability (“agency key”) and which model is currently used.
- Override fields to change models without code changes.

### How overrides work

- Defaults come from `shared/model_registry.json`
- Overrides are stored in SQLite:
  - Table: `model_overrides`
  - Keys are per supplier, per agency key

An override value of:
- **blank** means “use default”
- any text means “use this exact model id”

### Which parts can be overridden?

Agency keys (typical):

- `SCRIPT_PARSER`
- `DICTATION`
- `VOICE_ANALYZER`
- `AUTO_NARRATOR`
- `IMAGE_GEN`
- `VIDEO_GEN`
- `TTS_PREVIEW`

The provider uses:
- override (if present), otherwise default

### Reset to defaults

Reset deletes all overrides for that supplier:

- `POST /api/model-overrides/<supplier>/reset`

---

## 8) Voice identities

Voice identities let you:
- analyse a recorded voice to produce a reusable “voice DNA” text profile,
- store it under a label,
- and reuse it across renders.

### Where it lives

- Backend storage: SQLite table `voice_identities`
- CRUD endpoints:
  - `GET /api/voice-identities/<supplier>`
  - `POST /api/voice-identities/<supplier>`
  - `DELETE /api/voice-identities/<supplier>/<voice_id>`

### What a voice identity contains

- `label`: your human-friendly name (stored upper-case)
- `base_voice`: a base voice id (supplier-specific)
- `traits`: the “voice DNA” / acoustic signature paragraph
- `speed`: default speed for that identity
- `sentiment`: optional default sentiment

### Voice preview

The UI can trigger a short preview phrase using your selected voice settings.

- For Google, preview uses TTS model and returns audio that the browser plays.
- For OpenAI, preview uses the OpenAI TTS endpoint and plays audio in-browser.

---

## 9) Themes and UI scale

These are stored as global settings in the same SQLite database.

### Theme

- Values: `dark` or `light`
- Endpoints:
  - `GET /api/settings/theme`
  - `POST /api/settings/theme`

Stored in `app_settings` with key `theme`.

### UI scale

- Values: `normal` or `large`
- Endpoints:
  - `GET /api/settings/ui-scale`
  - `POST /api/settings/ui-scale`

Stored in `app_settings` with key `ui_scale`.

---

## 10) Data storage and security

### Where the database is

Default path:

- `data/syntaxmatrixdir/db.sqlite`

Override it with:

- `DATABASE_PATH=/absolute/or/relative/path/to/db.sqlite`

### What is stored in SQLite

- `app_settings` — supplier/theme/ui_scale
- `model_overrides` — model override values per supplier
- `api_credentials` — encrypted supplier keys
- `voice_identities` — stored voice profiles per supplier

### Encryption master key file

By default:

- `data/syntaxmatrixdir/.vd_master_key`

Recovery behaviour:
- If the master key file is missing but encrypted credentials exist, the app can regenerate a new master key and wipe credentials (meaning users must re-enter keys). See `data/credentials.py`.

---

## 11) Backend API reference

Base paths are served by the Flask app:

### Settings

- `GET  /api/settings/supplier` → `{ supplier }`
- `POST /api/settings/supplier` → `{ supplier }`

- `GET  /api/settings/theme` → `{ theme }`
- `POST /api/settings/theme` → `{ theme }`

- `GET  /api/settings/ui-scale` → `{ uiScale }`
- `POST /api/settings/ui-scale` → `{ uiScale }`

### Credentials

- `GET    /api/credentials/status` → `{ status: { google: boolean, openai: boolean } }`
- `POST   /api/credentials/<supplier>` → save key
- `DELETE /api/credentials/<supplier>` → delete key
- `GET    /api/credentials/<supplier>` → internal use (returns key to runtime store; do not show to users)

### Model overrides

- `GET  /api/model-overrides/<supplier>` → keys/defaults/overrides
- `POST /api/model-overrides/<supplier>` → save overrides
- `POST /api/model-overrides/<supplier>/reset` → reset

### Voice identities

- `GET    /api/voice-identities/<supplier>` → list identities
- `POST   /api/voice-identities/<supplier>` → create identity
- `DELETE /api/voice-identities/<supplier>/<voice_id>` → delete

---

## 12) Troubleshooting

### “ai.analyseVoice is not a function”
Cause: the method name is `analyzeVoice` (American spelling) in the provider interface.

Fix: replace `analyseVoice` with `analyzeVoice` in `components/Studio.tsx`, then rebuild your frontend bundle.

---

### “MISSING_API_KEY: Please add your Google key in API Interface Credentials.”
Cause: you have not saved a key (or the runtime store has not been warmed).

Fix:
1) Open **Model Blueprint → API Interface Credentials**
2) Paste and save the key
3) Refresh the page

---

### “OPENAI_API_KEY_MISSING”
Cause: OpenAI runtime key is not available in memory.

Fix: save the OpenAI key in **API Interface Credentials** and reload.

---

### Supplier changes not “sticking”
Supplier persistence is backend-driven (`app_settings.supplier`).

If it keeps reverting, check:
1) You are running the Flask server (to provide `/api/settings/supplier`)
2) Your UI actually POSTs `/api/settings/supplier` on change
3) You rebuilt `index.js` after making changes to `Studio.tsx`

---

### Changes to `.tsx` not showing up in browser
If your deployment serves a compiled `index.js`, any TSX changes require a rebuild.

Checklist:
- run your build step (Vite/esbuild)
- hard refresh (Ctrl+F5)
- confirm the server is serving the updated `index.js`

---

### SQLite “database is locked”
The DB connection enables WAL mode, but locks can still happen in some environments.

Fixes:
- put the database on a local disk/volume with proper file locking
- avoid running multiple copies of the server pointing at the same sqlite file without coordination
- keep DB on a mounted volume for containers, not inside an ephemeral layer

---

### Voice preview does not play
Common reasons:
- Browser autoplay restrictions (needs a user click)
- AudioContext suspended
- Missing/invalid key

Try:
- click the preview button again
- ensure the key is saved and valid
- test in Chrome/Edge first

---

## 13) FAQ

### Is my API key stored in the browser?
No. Keys are stored **encrypted in SQLite** and loaded into an in-memory runtime store at app start.

There is a small “legacy cleanup” that removes old keys from localStorage if they existed from earlier builds.

### Where are my settings saved?
In SQLite table `app_settings` under keys like `supplier`, `theme`, and `ui_scale`.

### Can multiple users have separate keys?
Not yet. Current storage is instance-wide (single set of supplier keys per deployment).

### Can I run without any keys at all?
You can open the UI, but generation features will fail until a key is added.

### What costs money?
Calls to:
- Google Gemini / Veo
- OpenAI models (including video)

You must enable billing in the relevant platform.

### How do I reset everything?
Stop the server and delete:
- `data/syntaxmatrixdir/db.sqlite`
- `data/syntaxmatrixdir/.vd_master_key`

Restart and re-enter keys/settings.

### Why does OpenAI sometimes “fall back” to Google video?
If OpenAI video returns a moderation/policy block, VisionDirector tries to complete the request using Google video generation so you can keep working.

---

## 14) Repo structure

High-value files:

- `components/Studio.tsx` — main Studio UI (supplier, narrative, vault, render)
- `components/ModelMap.tsx` — Model Blueprint (secure vault + overrides)
- `services/aiProvider.ts` — selects provider (google/openai) + fallback logic
- `services/geminiService.ts` — Google generation, voice analysis, TTS preview
- `services/openaiService.ts` — OpenAI generation, TTS, transcription, Sora
- `services/modelOverrides.ts` — override storage API client
- `services/runtimeKeys.ts` — runtime key cache (memory only)
- `api/model_overrides.py` — Flask endpoints for settings/overrides/credentials/voices
- `data/db.py` — sqlite connection and path management
- `data/credentials.py` — encrypted key storage
- `data/model_registry.py` — model registry + `app_settings` helpers
- `data/voice_identities.py` — voice identity CRUD
- `shared/model_registry.json` — default models per supplier

---

## 15) Questions for you

If you answer these, I can tighten this knowledgebase and make it match your exact build:

1) Which runtime is your “official” deployment target: **Flask**, **Node**, or **Docker**?
2) Do you want the knowledgebase to describe **logo management** (it currently exists in some builds as browser-stored branding), or should we treat branding as “not implemented yet”?
3) In the Asset Vault, do you want to officially support **video uploads**, or only video outputs + extension of generated clips?
4) Should the app expose a “Download output” button as a first-class workflow, or is the vault list sufficient?

---

**Version note:** This README reflects the code layout in `Vision_Director.zip` and the backend endpoints exposed via `api/model_overrides.py`.
