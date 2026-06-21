from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

marker = "# smx-visiondirector audio runtime method bindings"

if marker in content:
    print("Audio runtime method bindings already present.")
else:
    binding_block = dedent(
        '''
        # smx-visiondirector audio runtime method bindings
        #
        # These are attached explicitly to avoid fragile indentation when patching the
        # existing VisionDirectorAIRuntime class in small migration steps.
        def _smx_transcribe_audio_for_provider(
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


        def _smx_analyze_voice_for_provider(
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


        VisionDirectorAIRuntime.transcribe_audio_for_provider = _smx_transcribe_audio_for_provider
        VisionDirectorAIRuntime.analyze_voice_for_provider = _smx_analyze_voice_for_provider
        '''
    ).lstrip()

    content = content.rstrip() + "\n\n\n" + binding_block + "\n"
    runtime_file.write_text(content, encoding="utf-8")
    print("Bound audio runtime methods onto VisionDirectorAIRuntime.")
