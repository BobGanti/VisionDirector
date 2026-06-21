from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
init_file = Path("src/smx_visiondirector/__init__.py")
test_file = Path("tests/test_provider_backed_voice_preview.py")


# ---------------------------------------------------------------------
# Patch ai_runtime.py with provider-backed voice preview binding
# ---------------------------------------------------------------------
runtime = runtime_file.read_text(encoding="utf-8")

marker = "# smx-visiondirector provider-backed TTS preview bindings"
if marker not in runtime:
    block = dedent(
        r'''
        # smx-visiondirector provider-backed TTS preview bindings

        def _smx_normalize_voice_name(voice: Any, *, provider: str) -> str:
            if isinstance(voice, dict):
                for key in ("voiceName", "voice_name", "name", "id", "label", "value"):
                    value = voice.get(key)
                    if value:
                        voice = value
                        break

            raw = str(voice or "").strip()
            if not raw:
                return "Zephyr" if provider == "google" else "alloy"

            if provider == "openai":
                builtins = {
                    "alloy", "ash", "ballad", "coral", "echo", "fable",
                    "onyx", "nova", "sage", "shimmer", "verse", "marin", "cedar",
                }
                lower = raw.lower()
                if lower in builtins:
                    return lower

                # Common Gemini voice labels mapped to distinct OpenAI built-ins
                # only when the UI is currently showing Google-style names.
                google_to_openai = {
                    "zephyr": "alloy",
                    "puck": "echo",
                    "charon": "onyx",
                    "kore": "nova",
                    "fenrir": "ash",
                    "leda": "shimmer",
                    "orus": "sage",
                    "aoede": "coral",
                    "callirrhoe": "fable",
                    "autonoe": "verse",
                    "enceladus": "ballad",
                    "iapetus": "marin",
                    "umbriel": "cedar",
                }
                return google_to_openai.get(lower, "alloy")

            return raw


        def _smx_speed_multiplier(speed: str | None) -> float:
            value = str(speed or "natural").strip().lower()
            if value in {"slow", "slower"}:
                return 0.85
            if value in {"fast", "faster"}:
                return 1.15
            return 1.0


        def _smx_binary_response_bytes(response: Any) -> bytes:
            if isinstance(response, bytes):
                return response
            if isinstance(response, bytearray):
                return bytes(response)

            content = getattr(response, "content", None)
            if isinstance(content, bytes):
                return content
            if isinstance(content, bytearray):
                return bytes(content)

            read = getattr(response, "read", None)
            if callable(read):
                data = read()
                if isinstance(data, bytes):
                    return data
                if isinstance(data, bytearray):
                    return bytes(data)

            iter_bytes = getattr(response, "iter_bytes", None)
            if callable(iter_bytes):
                return b"".join(iter_bytes())

            raise VisionDirectorAIExecutionError("TTS_PREVIEW_NO_AUDIO_BYTES")


        def _smx_extract_google_audio_data_url(response: Any) -> str:
            candidates = _get_value(response, "candidates") or []
            for candidate in candidates:
                content = _get_value(candidate, "content")
                parts = _get_value(content, "parts") or []
                for part in parts:
                    inline = (
                        _get_value(part, "inline_data")
                        or _get_value(part, "inlineData")
                    )
                    if not inline:
                        continue

                    data = _get_value(inline, "data")
                    if not data:
                        continue

                    mime_type = (
                        _get_value(inline, "mime_type")
                        or _get_value(inline, "mimeType")
                        or "audio/wav"
                    )
                    return f"data:{mime_type};base64,{data}"

            raise VisionDirectorAIExecutionError("TTS_PREVIEW_NO_AUDIO_RETURNED")


        def _smx_google_voice_preview(
            profile: ProviderProfile,
            *,
            model: str,
            voice: Any,
            speed: str,
            traits: str,
            text: str,
        ) -> str:
            client = profile.client
            models = getattr(client, "models", None)
            generate = getattr(models, "generate_content", None) if models is not None else None
            if generate is None:
                generate = getattr(models, "generateContent", None) if models is not None else None
            if generate is None:
                raise VisionDirectorAIExecutionError("Google host client does not support generate_content.")

            voice_name = _smx_normalize_voice_name(voice, provider="google")
            prompt = (
                f"Read this preview using the selected voice. "
                f"Voice style notes: {traits or 'clear natural delivery'}. "
                f"Speed: {speed or 'natural'}. "
                f"Text to speak: {text or voice_name}."
            )

            try:
                from google.genai import types  # type: ignore

                config = types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    ),
                )
            except Exception:
                config = {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice_name,
                            }
                        }
                    },
                }

            try:
                response = generate(
                    model=model,
                    contents=prompt,
                    config=config,
                )
            except Exception as exc:
                raise VisionDirectorAIExecutionError(str(exc)) from exc

            return _smx_extract_google_audio_data_url(response)


        def _smx_openai_voice_preview(
            profile: ProviderProfile,
            *,
            model: str,
            voice: Any,
            speed: str,
            traits: str,
            text: str,
        ) -> str:
            client = profile.client
            audio = getattr(client, "audio", None)
            speech = getattr(audio, "speech", None) if audio is not None else None
            create = getattr(speech, "create", None) if speech is not None else None
            if create is None:
                raise VisionDirectorAIExecutionError("OpenAI host client does not support audio speech.")

            voice_name = _smx_normalize_voice_name(voice, provider="openai")
            speech_text = text or str(voice_name)
            instructions = traits or "Speak clearly and naturally."

            try:
                response = create(
                    model=model,
                    voice=voice_name,
                    input=speech_text,
                    instructions=instructions,
                    response_format="wav",
                    speed=_smx_speed_multiplier(speed),
                )
            except TypeError:
                response = create(
                    model=model,
                    voice=voice_name,
                    input=speech_text,
                    response_format="wav",
                    speed=_smx_speed_multiplier(speed),
                )
            except Exception as exc:
                raise VisionDirectorAIExecutionError(str(exc)) from exc

            audio_bytes = _smx_binary_response_bytes(response)
            b64 = base64.b64encode(audio_bytes).decode("ascii")
            return f"data:audio/wav;base64,{b64}"


        def _smx_preview_voice_for_provider(
            self,
            *,
            provider: str,
            voice: Any,
            speed: str = "natural",
            traits: str = "",
            text: str = "Identity verified.",
            model: str | None = None,
            operation: str = "voice_preview",
        ) -> dict[str, Any]:
            clean_provider = str(provider or "").strip().lower()
            profile = self.profile_registry.require_provider(clean_provider)

            selected_model = model or profile.model
            if not selected_model:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host AI profile for provider '{profile.provider}' has no model."
                )

            started_at = utc_now()
            status = "success"
            tokens = TokenBreakdown()

            try:
                if profile.provider == "google":
                    audio_url = _smx_google_voice_preview(
                        profile,
                        model=selected_model,
                        voice=voice,
                        speed=speed,
                        traits=traits,
                        text=text,
                    )
                elif profile.provider == "openai":
                    audio_url = _smx_openai_voice_preview(
                        profile,
                        model=selected_model,
                        voice=voice,
                        speed=speed,
                        traits=traits,
                        text=text,
                    )
                else:
                    raise VisionDirectorAIExecutionError(
                        f"Unsupported VisionDirector voice preview provider: {profile.provider}"
                    )

                return {
                    "audio_url": audio_url,
                    "provider": profile.provider,
                    "model": selected_model,
                }
            except Exception:
                status = "error"
                raise
            finally:
                record_usage = getattr(self, "_record_usage", None)
                if callable(record_usage):
                    record_usage(
                        operation=operation,
                        role=profile.role or clean_provider,
                        provider=profile.provider,
                        model=selected_model,
                        status=status,
                        started_at=started_at,
                        tokens=tokens,
                    )


        VisionDirectorAIRuntime.preview_voice_for_provider = _smx_preview_voice_for_provider
        '''
    ).lstrip()

    runtime = runtime.rstrip() + "\n\n\n" + block + "\n"
    runtime_file.write_text(runtime, encoding="utf-8")
    print("added provider-backed TTS preview runtime binding")
else:
    print("provider-backed TTS preview runtime binding already present")


# ---------------------------------------------------------------------
# Patch __init__.py route
# ---------------------------------------------------------------------
init = init_file.read_text(encoding="utf-8")

if '@bp.post("/api/ai/preview-voice")' not in init:
    anchor = '    @bp.post("/api/ai/generate-video")'
    idx = init.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find generate-video route anchor.")

    route = dedent(
        '''
            @bp.post("/api/ai/preview-voice")
            def ai_preview_voice():
                data = request.get_json(silent=True) or {}
                supplier = str(data.get("supplier") or "google").strip().lower()
                voice = data.get("voice") or "Zephyr"
                speed = str(data.get("speed") or "natural")
                traits = str(data.get("traits") or "")
                text = str(data.get("text") or "Identity verified.")

                model = model_router.ModelRouter(
                    profile_registry=profile_registry,
                    overrides_store=_model_overrides_snapshot(),
                ).resolve(supplier, "TTS_PREVIEW").model

                try:
                    result = build_ai_runtime(
                        profile_registry,
                        usage_recorder=resolved_usage_recorder,
                    ).preview_voice_for_provider(
                        provider=supplier,
                        voice=voice,
                        speed=speed,
                        traits=traits,
                        text=text,
                        model=model,
                        operation="voice_preview",
                    )
                except VisionDirectorAIProfileError as exc:
                    return {"error": str(exc)}, 503
                except VisionDirectorAIExecutionError as exc:
                    return {"error": str(exc)}, 502

                return {
                    "audioUrl": result["audio_url"],
                    "supplier": result["provider"],
                    "model": result["model"],
                }


        '''
    )

    init = init[:idx] + route + init[idx:]
    init_file.write_text(init, encoding="utf-8")
    print("added /api/ai/preview-voice route")
else:
    print("/api/ai/preview-voice route already present")


# ---------------------------------------------------------------------
# Patch runtime JS by adding a final provider-backed override
# ---------------------------------------------------------------------
init = init_file.read_text(encoding="utf-8")

if "__smxVisionDirectorProviderVoicePreview" not in init:
    patch_anchor = '        "try {",\n        \'  if (typeof googleProvider !== "undefined") {\','
    idx = init.find(patch_anchor)
    if idx < 0:
        raise SystemExit("Could not find runtime JS patch try-anchor.")

    js = dedent(
        r'''
        async function __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, supplier) {
          const res = await fetch("/visiondirector/api/ai/preview-voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ supplier, voice, speed, traits, text })
          });
          const data = await res.json().catch(() => null);
          if (!res.ok) {
            throw new Error(data?.error || `VISIONDIRECTOR_VOICE_PREVIEW_FAILED: ${res.status}`);
          }
          const audioUrl = data?.audioUrl;
          if (!audioUrl) {
            throw new Error("VISIONDIRECTOR_VOICE_PREVIEW_NO_AUDIO");
          }
          const audio = new Audio(audioUrl);
          await audio.play();
        }

        try {
          if (typeof googleProvider !== "undefined") {
            googleProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "google");
          }
          if (typeof openaiProvider !== "undefined") {
            openaiProvider.playVoicePreview = (voice, speed, traits, text) => __smxVisionDirectorProviderVoicePreview(voice, speed, traits, text, "openai");
          }
        } catch (error) {
          console.warn("[smx-visiondirector] Failed to install provider-backed voice preview patch", error);
        }

        '''
    ).strip("\n")

    entries = "\n".join("        " + repr(line) + "," for line in js.splitlines()) + "\n"
    init = init[:idx] + entries + init[idx:]
    init_file.write_text(init, encoding="utf-8")
    print("added provider-backed runtime voice preview override")
else:
    print("provider-backed runtime voice preview override already present")


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------
test_file.write_text(
    dedent(
        r'''
        from __future__ import annotations

        import base64

        from flask import Flask

        from smx_visiondirector import setup_visiondirector


        class FakeGoogleModels:
            def __init__(self):
                self.calls = []

            def generate_content(self, **kwargs):
                self.calls.append(kwargs)
                audio_b64 = base64.b64encode(b"google voice audio").decode("ascii")
                inline = type("Inline", (), {"data": audio_b64, "mime_type": "audio/wav"})()
                part = type("Part", (), {"inline_data": inline})()
                content = type("Content", (), {"parts": [part]})()
                candidate = type("Candidate", (), {"content": content})()
                return type("GoogleTTSResponse", (), {"candidates": [candidate]})()


        class FakeGoogleClient:
            def __init__(self):
                self.models = FakeGoogleModels()


        class FakeOpenAISpeech:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return b"openai voice audio"


        class FakeOpenAIAudio:
            def __init__(self):
                self.speech = FakeOpenAISpeech()


        class FakeOpenAIClient:
            def __init__(self):
                self.audio = FakeOpenAIAudio()


        def test_runtime_voice_preview_uses_provider_backend_not_browser_only(tmp_path):
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {"provider": "google", "model": "google-main", "client": FakeGoogleClient()},
                    "assistant": {"provider": "openai", "model": "openai-main", "client": FakeOpenAIClient()},
                },
            )

            response = app.test_client().get("/visiondirector/index.js")

            assert response.status_code == 200
            js = response.get_data(as_text=True)
            assert "__smxVisionDirectorProviderVoicePreview" in js
            assert "/visiondirector/api/ai/preview-voice" in js
            assert "new Audio(audioUrl)" in js
            assert "googleProvider.playVoicePreview" in js
            assert "openaiProvider.playVoicePreview" in js


        def test_google_voice_preview_route_returns_provider_audio_and_uses_selected_voice(tmp_path):
            fake = FakeGoogleClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={"main": {"provider": "google", "model": "google-main", "client": fake}},
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/preview-voice",
                json={
                    "supplier": "google",
                    "voice": "Puck",
                    "speed": "natural",
                    "traits": "warm delivery",
                    "text": "Puck",
                },
            )

            assert response.status_code == 200
            body = response.get_json()
            assert body["audioUrl"].startswith("data:audio/wav;base64,")
            assert fake.models.calls
            assert fake.models.calls[-1]["model"]
            assert "Puck" in str(fake.models.calls[-1]["config"])


        def test_openai_voice_preview_route_returns_provider_audio_and_uses_selected_voice(tmp_path):
            fake = FakeOpenAIClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={"main": {"provider": "openai", "model": "openai-main", "client": fake}},
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/preview-voice",
                json={
                    "supplier": "openai",
                    "voice": "nova",
                    "speed": "fast",
                    "traits": "bright delivery",
                    "text": "nova",
                },
            )

            assert response.status_code == 200
            body = response.get_json()
            assert body["audioUrl"].startswith("data:audio/wav;base64,")
            assert fake.audio.speech.calls
            call = fake.audio.speech.calls[-1]
            assert call["voice"] == "nova"
            assert call["input"] == "nova"
            assert call["response_format"] == "wav"
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("created tests/test_provider_backed_voice_preview.py")
