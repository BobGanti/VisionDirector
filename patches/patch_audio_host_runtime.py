from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
test_file = ROOT / "tests" / "test_audio_host_runtime_patch.py"


# -------------------------
# Patch ai_runtime.py
# -------------------------
runtime = runtime_file.read_text(encoding="utf-8")

if "import io" not in runtime:
    runtime = runtime.replace("import base64\n", "import base64\nimport io\n", 1)

if "class AIAudioTextResult" not in runtime:
    marker = "@dataclass(frozen=True)\nclass AIVideoResult:"
    idx = runtime.find(marker)
    if idx < 0:
        raise SystemExit("Could not find AIVideoResult dataclass insertion point.")

    dataclass_block = dedent(
        '''
        @dataclass(frozen=True)
        class AIAudioTextResult:
            role: str
            provider: str
            model: str | None
            text: str
            tokens: TokenBreakdown


        '''
    )
    runtime = runtime[:idx] + dataclass_block + runtime[idx:]
    print("added AIAudioTextResult")


if "def transcribe_audio_for_provider(" not in runtime:
    marker = "    def generate_video_for_provider("
    idx = runtime.find(marker)
    if idx < 0:
        raise SystemExit("Could not find generate_video_for_provider insertion point.")

    methods = dedent(
        '''
            def transcribe_audio_for_provider(
                self,
                *,
                provider: str,
                audio_base64: str,
                model: str | None = None,
                operation: str = "transcribe_audio",
            ) -> AIAudioTextResult:
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
                        provider_result = _generate_google_audio_text(
                            profile,
                            model=selected_model,
                            audio_base64=audio_base64,
                            prompt="Transcribe this audio exactly. Return only the transcript text.",
                        )
                    elif profile.provider == "openai":
                        provider_result = _generate_openai_audio_transcription(
                            profile,
                            model=selected_model,
                            audio_base64=audio_base64,
                        )
                    else:
                        raise VisionDirectorAIExecutionError(
                            f"Unsupported VisionDirector audio provider: {profile.provider}"
                        )

                    tokens = provider_result.tokens
                    return AIAudioTextResult(
                        role=profile.role or clean_provider,
                        provider=profile.provider,
                        model=selected_model,
                        text=provider_result.text,
                        tokens=tokens,
                    )
                except Exception:
                    status = "error"
                    raise
                finally:
                    self._record_usage(
                        operation=operation,
                        role=profile.role or clean_provider,
                        provider=profile.provider,
                        model=selected_model,
                        status=status,
                        started_at=started_at,
                        tokens=tokens,
                    )

            def analyze_voice_for_provider(
                self,
                *,
                provider: str,
                audio_base64: str,
                sentiment: str = "neutral",
                model: str | None = None,
                dictation_model: str | None = None,
                operation: str = "analyze_voice",
            ) -> AIAudioTextResult:
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

                prompt = (
                    "ACT AS A VOCAL FORENSIC ANALYST. Extract the acoustic signature for high-fidelity "
                    "voice direction. Identify timbre, resonance, accent/dialect markers, emotional baseline, "
                    f"cadence, pacing, and delivery style. Target sentiment: {sentiment}. "
                    "Return one concise Acoustic Signature paragraph only."
                )

                try:
                    if profile.provider == "google":
                        provider_result = _generate_google_audio_text(
                            profile,
                            model=selected_model,
                            audio_base64=audio_base64,
                            prompt=prompt,
                        )
                    elif profile.provider == "openai":
                        transcript_result = _generate_openai_audio_transcription(
                            profile,
                            model=dictation_model or "whisper-1",
                            audio_base64=audio_base64,
                        )
                        provider_result = _generate_openai_text_response(
                            profile,
                            model=selected_model,
                            prompt=(
                                f"Sentiment: {sentiment}\\n"
                                f"Transcript:\\n{transcript_result.text}\\n\\n"
                                "Produce a concise voice-style descriptor for TTS/video direction. "
                                "Return plain text only."
                            ),
                        )
                    else:
                        raise VisionDirectorAIExecutionError(
                            f"Unsupported VisionDirector audio provider: {profile.provider}"
                        )

                    tokens = provider_result.tokens
                    return AIAudioTextResult(
                        role=profile.role or clean_provider,
                        provider=profile.provider,
                        model=selected_model,
                        text=provider_result.text,
                        tokens=tokens,
                    )
                except Exception:
                    status = "error"
                    raise
                finally:
                    self._record_usage(
                        operation=operation,
                        role=profile.role or clean_provider,
                        provider=profile.provider,
                        model=selected_model,
                        status=status,
                        started_at=started_at,
                        tokens=tokens,
                    )


        '''
    )
    runtime = runtime[:idx] + methods + runtime[idx:]
    print("added audio runtime methods")
else:
    print("audio runtime methods already present")


if "def _extract_audio_inline_data(" not in runtime:
    marker = "\ndef _generate_google_video("
    idx = runtime.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _generate_google_video insertion point.")

    helpers = dedent(
        '''
        def _extract_audio_inline_data(audio_base64: str) -> tuple[str, str, bytes]:
            raw = str(audio_base64 or "").strip()
            mime_type = "audio/wav"
            payload = raw

            if raw.startswith("data:") and "," in raw:
                header, payload = raw.split(",", 1)
                declared = header[5:].split(";", 1)[0].strip()
                if declared:
                    mime_type = declared

            try:
                audio_bytes = base64.b64decode(payload)
            except Exception as exc:
                raise VisionDirectorAIExecutionError("INVALID_AUDIO_BASE64") from exc

            if not audio_bytes:
                raise VisionDirectorAIExecutionError("EMPTY_AUDIO_PAYLOAD")

            return payload, mime_type, audio_bytes


        def _generate_google_audio_text(
            profile: ProviderProfile,
            *,
            model: str,
            audio_base64: str,
            prompt: str,
        ) -> _ProviderTextResponse:
            client = profile.client
            models = getattr(client, "models", None)
            if models is None:
                raise VisionDirectorAIExecutionError("Google host client has no models interface.")

            generate = getattr(models, "generate_content", None) or getattr(models, "generateContent", None)
            if generate is None:
                raise VisionDirectorAIExecutionError("Google host client does not support generate_content.")

            audio_payload, mime_type, audio_bytes = _extract_audio_inline_data(audio_base64)

            contents: Any
            try:
                from google.genai import types  # type: ignore

                contents = [
                    prompt,
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                ]
            except Exception:
                contents = {
                    "parts": [
                        {"inlineData": {"data": audio_payload, "mimeType": mime_type}},
                        {"text": prompt},
                    ]
                }

            try:
                response = generate(model=model, contents=contents)
            except Exception as exc:
                raise VisionDirectorAIExecutionError(str(exc)) from exc

            return _ProviderTextResponse(
                text=str(_get_value(response, "text") or "").strip(),
                tokens=extract_token_breakdown(response),
            )


        def _generate_openai_audio_transcription(
            profile: ProviderProfile,
            *,
            model: str,
            audio_base64: str,
        ) -> _ProviderTextResponse:
            client = profile.client
            audio = getattr(client, "audio", None)
            transcriptions = getattr(audio, "transcriptions", None) if audio is not None else None
            create = getattr(transcriptions, "create", None) if transcriptions is not None else None
            if create is None:
                raise VisionDirectorAIExecutionError("OpenAI host client does not support audio transcription.")

            _, mime_type, audio_bytes = _extract_audio_inline_data(audio_base64)
            ext = "wav"
            if "mpeg" in mime_type or "mp3" in mime_type:
                ext = "mp3"
            elif "mp4" in mime_type or "m4a" in mime_type:
                ext = "m4a"
            elif "webm" in mime_type:
                ext = "webm"

            file_obj = io.BytesIO(audio_bytes)
            file_obj.name = f"audio.{ext}"

            try:
                response = create(model=model, file=file_obj)
            except Exception as exc:
                raise VisionDirectorAIExecutionError(str(exc)) from exc

            return _ProviderTextResponse(
                text=str(_get_value(response, "text") or "").strip(),
                tokens=extract_token_breakdown(response),
            )


        def _generate_openai_text_response(
            profile: ProviderProfile,
            *,
            model: str,
            prompt: str,
        ) -> _ProviderTextResponse:
            client = profile.client
            responses = getattr(client, "responses", None)
            create = getattr(responses, "create", None) if responses is not None else None
            if create is None:
                raise VisionDirectorAIExecutionError("OpenAI host client does not support Responses API.")

            try:
                response = create(
                    model=model,
                    input=prompt,
                )
            except Exception as exc:
                raise VisionDirectorAIExecutionError(str(exc)) from exc

            text = (
                _get_value(response, "output_text")
                or _get_value(response, "text")
                or ""
            )
            if not text:
                output = _get_value(response, "output") or []
                fragments: list[str] = []
                for item in output if isinstance(output, list) else []:
                    content = _get_value(item, "content") or []
                    for part in content if isinstance(content, list) else []:
                        value = _get_value(part, "text")
                        if value:
                            fragments.append(str(value))
                text = "\\n".join(fragments)

            return _ProviderTextResponse(
                text=str(text or "").strip(),
                tokens=extract_token_breakdown(response),
            )


        '''
    ).lstrip()

    runtime = runtime[:idx] + "\n" + helpers + runtime[idx:]
    print("added audio provider helpers")
else:
    print("audio provider helpers already present")


runtime_file.write_text(runtime, encoding="utf-8")


# -------------------------
# Patch __init__.py routes and runtime JS
# -------------------------
init = init_file.read_text(encoding="utf-8")

if '@bp.post("/api/ai/transcribe-audio")' not in init:
    marker = '    @bp.post("/api/ai/generate-video")'
    idx = init.find(marker)
    if idx < 0:
        raise SystemExit("Could not find generate-video route insertion point.")

    routes = dedent(
        '''
            @bp.post("/api/ai/transcribe-audio")
            def ai_transcribe_audio():
                data = request.get_json(silent=True) or {}
                supplier = str(data.get("supplier") or "google").strip().lower()
                audio_base64 = str(
                    data.get("audioBase64")
                    or data.get("audioDataUrl")
                    or data.get("audio")
                    or ""
                )

                if not audio_base64:
                    return {"error": "AUDIO_PAYLOAD_REQUIRED"}, 400

                model = ModelRouter(
                    profile_registry=profile_registry,
                    overrides_store=_model_overrides_snapshot(),
                ).resolve(supplier, "DICTATION").model

                try:
                    result = build_ai_runtime(
                        profile_registry,
                        usage_recorder=resolved_usage_recorder,
                    ).transcribe_audio_for_provider(
                        provider=supplier,
                        audio_base64=audio_base64,
                        model=model,
                        operation="transcribe_audio",
                    )
                except VisionDirectorAIProfileError as exc:
                    return {"error": str(exc)}, 503
                except VisionDirectorAIExecutionError as exc:
                    return {"error": str(exc)}, 502

                return {
                    "text": result.text,
                    "supplier": result.provider,
                    "model": result.model,
                }


            @bp.post("/api/ai/analyze-voice")
            def ai_analyze_voice():
                data = request.get_json(silent=True) or {}
                supplier = str(data.get("supplier") or "google").strip().lower()
                audio_base64 = str(
                    data.get("audioBase64")
                    or data.get("audioDataUrl")
                    or data.get("audio")
                    or ""
                )
                sentiment = str(data.get("sentiment") or "neutral")

                if not audio_base64:
                    return {"error": "AUDIO_PAYLOAD_REQUIRED"}, 400

                router = ModelRouter(
                    profile_registry=profile_registry,
                    overrides_store=_model_overrides_snapshot(),
                )
                model = router.resolve(supplier, "VOICE_ANALYZER").model
                dictation_model = router.resolve(supplier, "DICTATION").model

                try:
                    result = build_ai_runtime(
                        profile_registry,
                        usage_recorder=resolved_usage_recorder,
                    ).analyze_voice_for_provider(
                        provider=supplier,
                        audio_base64=audio_base64,
                        sentiment=sentiment,
                        model=model,
                        dictation_model=dictation_model,
                        operation="analyze_voice",
                    )
                except VisionDirectorAIProfileError as exc:
                    return {"error": str(exc)}, 503
                except VisionDirectorAIExecutionError as exc:
                    return {"error": str(exc)}, 502

                return {
                    "traits": result.text,
                    "supplier": result.provider,
                    "model": result.model,
                }


        '''
    )

    init = init[:idx] + routes + init[idx:]
    print("added audio backend routes")
else:
    print("audio backend routes already present")


def js_list_entries(js: str) -> list[str]:
    return ["        " + repr(line) + "," for line in js.splitlines()]


if "__smxVisionDirectorTranscribeAudio" not in init:
    anchor = '        "async function __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, supplier) {",'
    idx = init.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find JS generate-video helper anchor.")

    helper_js = dedent(
        r'''
        async function __smxVisionDirectorTranscribeAudio(audioBase64, supplier) {
          const res = await fetch("/visiondirector/api/ai/transcribe-audio", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ supplier, audioBase64 })
          });
          const data = await res.json().catch(() => null);
          if (!res.ok) {
            throw new Error(data?.error || `VISIONDIRECTOR_TRANSCRIBE_AUDIO_FAILED: ${res.status}`);
          }
          return String(data?.text || "");
        }

        async function __smxVisionDirectorAnalyzeVoice(audioBase64, sentiment, supplier) {
          const res = await fetch("/visiondirector/api/ai/analyze-voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ supplier, audioBase64, sentiment })
          });
          const data = await res.json().catch(() => null);
          if (!res.ok) {
            throw new Error(data?.error || `VISIONDIRECTOR_ANALYZE_VOICE_FAILED: ${res.status}`);
          }
          return String(data?.traits || "");
        }

        '''
    ).strip("\n")

    block = "\n".join(js_list_entries(helper_js)) + "\n"
    init = init[:idx] + block + init[idx:]
    print("added audio JS helpers")
else:
    print("audio JS helpers already present")


if "googleProvider.analyzeVoice" not in init:
    lines = init.splitlines()
    for i, line in enumerate(lines):
        if "googleProvider.generateImage =" in line:
            lines.insert(i + 1, "        " + repr('    googleProvider.analyzeVoice = (audioBase64, sentiment) => __smxVisionDirectorAnalyzeVoice(audioBase64, sentiment, "google");') + ",")
            lines.insert(i + 2, "        " + repr('    googleProvider.transcribeAudio = (audioBase64) => __smxVisionDirectorTranscribeAudio(audioBase64, "google");') + ",")
            init = "\n".join(lines) + "\n"
            print("added google audio overrides")
            break
    else:
        raise SystemExit("Could not find googleProvider.generateImage override.")
else:
    print("google audio overrides already present")


if "openaiProvider.analyzeVoice" not in init:
    lines = init.splitlines()
    for i, line in enumerate(lines):
        if "openaiProvider.generateImage =" in line:
            lines.insert(i + 1, "        " + repr('    openaiProvider.analyzeVoice = (audioBase64, sentiment) => __smxVisionDirectorAnalyzeVoice(audioBase64, sentiment, "openai");') + ",")
            lines.insert(i + 2, "        " + repr('    openaiProvider.transcribeAudio = (audioBase64) => __smxVisionDirectorTranscribeAudio(audioBase64, "openai");') + ",")
            init = "\n".join(lines) + "\n"
            print("added openai audio overrides")
            break
    else:
        raise SystemExit("Could not find openaiProvider.generateImage override.")
else:
    print("openai audio overrides already present")


init_file.write_text(init, encoding="utf-8")


# -------------------------
# Tests
# -------------------------
test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import base64

        from flask import Flask

        from smx_visiondirector import setup_visiondirector


        AUDIO_DATA_URL = "data:audio/wav;base64," + base64.b64encode(b"fake-audio").decode("ascii")


        class FakeGoogleModels:
            def __init__(self):
                self.calls = []

            def generate_content(self, **kwargs):
                self.calls.append(kwargs)
                return type("GoogleTextResponse", (), {"text": "fake google audio text"})()


        class FakeGoogleClient:
            def __init__(self):
                self.models = FakeGoogleModels()


        class FakeOpenAITranscriptions:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return type("OpenAITranscript", (), {"text": "fake openai transcript"})()


        class FakeOpenAIAudio:
            def __init__(self):
                self.transcriptions = FakeOpenAITranscriptions()


        class FakeOpenAIResponses:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return type("OpenAIResponse", (), {"output_text": "fake openai voice traits"})()


        class FakeOpenAIClient:
            def __init__(self):
                self.audio = FakeOpenAIAudio()
                self.responses = FakeOpenAIResponses()


        def test_runtime_js_overrides_audio_methods_to_host_backend(tmp_path):
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
            assert "__smxVisionDirectorTranscribeAudio" in js
            assert "__smxVisionDirectorAnalyzeVoice" in js
            assert "googleProvider.analyzeVoice" in js
            assert "googleProvider.transcribeAudio" in js
            assert "openaiProvider.analyzeVoice" in js
            assert "openaiProvider.transcribeAudio" in js


        def test_google_transcribe_audio_route_uses_host_client(tmp_path):
            fake = FakeGoogleClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={"main": {"provider": "google", "model": "google-main", "client": fake}},
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/transcribe-audio",
                json={"supplier": "google", "audioBase64": AUDIO_DATA_URL},
            )

            assert response.status_code == 200
            assert response.get_json()["text"] == "fake google audio text"
            assert fake.models.calls
            assert fake.models.calls[-1]["model"]


        def test_google_analyze_voice_route_uses_host_client(tmp_path):
            fake = FakeGoogleClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={"main": {"provider": "google", "model": "google-main", "client": fake}},
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/analyze-voice",
                json={"supplier": "google", "audioBase64": AUDIO_DATA_URL, "sentiment": "joyful"},
            )

            assert response.status_code == 200
            assert response.get_json()["traits"] == "fake google audio text"
            assert fake.models.calls
            call_text = str(fake.models.calls[-1]["contents"])
            assert "VOCAL FORENSIC ANALYST" in call_text
            assert "joyful" in call_text


        def test_openai_audio_routes_use_host_client(tmp_path):
            fake = FakeOpenAIClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={"main": {"provider": "openai", "model": "openai-main", "client": fake}},
            )

            transcribe = app.test_client().post(
                "/visiondirector/api/ai/transcribe-audio",
                json={"supplier": "openai", "audioBase64": AUDIO_DATA_URL},
            )
            analyze = app.test_client().post(
                "/visiondirector/api/ai/analyze-voice",
                json={"supplier": "openai", "audioBase64": AUDIO_DATA_URL, "sentiment": "neutral"},
            )

            assert transcribe.status_code == 200
            assert transcribe.get_json()["text"] == "fake openai transcript"
            assert analyze.status_code == 200
            assert analyze.get_json()["traits"] == "fake openai voice traits"
            assert fake.audio.transcriptions.calls
            assert fake.responses.calls
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("created tests/test_audio_host_runtime_patch.py")
