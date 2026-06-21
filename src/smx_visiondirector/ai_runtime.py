from __future__ import annotations

import urllib.error
import urllib.request
import json
import base64
import io
import time
import tempfile
from urllib import request as urlrequest

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ai_profiles import (
    AIProfileRegistry,
    ProviderProfile,
    VisionDirectorAIProfileError,
)
from .usage import (
    TokenBreakdown,
    UsageRecorder,
    extract_token_breakdown,
    new_usage_event,
    utc_now,
)


class VisionDirectorAIExecutionError(RuntimeError):
    """Raised when a host-provided AI client cannot execute the request."""


@dataclass(frozen=True)
class AITextResult:
    role: str
    provider: str
    model: str | None
    text: str
    tokens: TokenBreakdown


@dataclass(frozen=True)
class AIImageResult:
    role: str
    provider: str
    model: str | None
    image_data_url: str | None
    tokens: TokenBreakdown



@dataclass(frozen=True)
class AIAudioTextResult:
    role: str
    provider: str
    model: str | None
    text: str
    tokens: TokenBreakdown


@dataclass(frozen=True)
class AIVideoResult:
    role: str
    provider: str
    model: str | None
    video_url: str | None
    video_ref: Any
    tokens: TokenBreakdown


@dataclass(frozen=True)
class _ProviderVideoResponse:
    video_url: str | None
    video_ref: Any
    tokens: TokenBreakdown


@dataclass(frozen=True)
class _ProviderTextResponse:
    text: str
    tokens: TokenBreakdown


@dataclass(frozen=True)
class _ProviderImageResponse:
    image_data_url: str | None
    tokens: TokenBreakdown


_GOOGLE_VIDEO_EXTENSION_HANDLES: dict[str, Any] = {}
_OPENAI_VIDEO_EXTENSION_HANDLES: dict[str, bytes] = {}
_OPENAI_VIDEO_EXTENSION_PROVIDER_IDS: dict[str, str] = {}


def _new_google_video_extension_handle(video: Any) -> str:
    handle = f"google-video-{__import__('uuid').uuid4().hex}"
    _GOOGLE_VIDEO_EXTENSION_HANDLES[handle] = video

    # Keep the dev server memory bounded. This is only an opaque runtime bridge,
    # not durable storage.
    if len(_GOOGLE_VIDEO_EXTENSION_HANDLES) > 64:
        oldest = next(iter(_GOOGLE_VIDEO_EXTENSION_HANDLES))
        _GOOGLE_VIDEO_EXTENSION_HANDLES.pop(oldest, None)

    return handle


def _extract_google_video_extension_handle(value: Any) -> str | None:
    if isinstance(value, dict):
        raw = value.get("extensionHandle") or value.get("extension_handle")
        return str(raw).strip() if raw else None

    if isinstance(value, str) and value.startswith("google-video-"):
        return value.strip()

    return None



class VisionDirectorAIRuntime:
    """Executes AI work using host-provided model clients only."""

    def __init__(
        self,
        profile_registry: AIProfileRegistry,
        *,
        usage_recorder: UsageRecorder | None = None,
    ):
        self.profile_registry = profile_registry
        self.usage_recorder = usage_recorder

    def generate_text(
        self,
        *,
        prompt: str,
        role: str = "main",
        model: str | None = None,
        operation: str = "generate_text",
    ) -> AITextResult:
        profile = self.profile_registry.require_role(role)
        return self._generate_text_with_profile(
            profile=profile,
            prompt=prompt,
            role=role,
            model=model,
            operation=operation,
        )

    def generate_text_for_provider(
        self,
        *,
        prompt: str,
        provider: str,
        model: str | None = None,
        operation: str = "generate_text",
    ) -> AITextResult:
        clean_provider = str(provider or "").strip().lower()
        profile = self.profile_registry.require_provider(clean_provider)
        return self._generate_text_with_profile(
            profile=profile,
            prompt=prompt,
            role=profile.role or clean_provider,
            model=model,
            operation=operation,
        )

    def generate_image_for_provider(
        self,
        *,
        prompt: str,
        provider: str,
        aspect_ratio: str = "9:16",
        model: str | None = None,
        operation: str = "generate_image",
    ) -> AIImageResult:
        clean_provider = str(provider or "").strip().lower()
        profile = self.profile_registry.require_provider(clean_provider)

        clean_prompt = str(prompt or "").strip()
        selected_model = model or profile.model

        if not clean_prompt:
            return AIImageResult(
                role=profile.role or clean_provider,
                provider=profile.provider,
                model=selected_model,
                image_data_url=None,
                tokens=TokenBreakdown(),
            )

        if not selected_model:
            raise VisionDirectorAIProfileError(
                f"VisionDirector host AI profile for provider '{profile.provider}' has no model."
            )

        started_at = utc_now()
        status = "success"
        tokens = TokenBreakdown()

        try:
            if profile.provider == "google":
                provider_result = _generate_google_image(
                    profile,
                    prompt=clean_prompt,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                )
            elif profile.provider == "openai":
                provider_result = _generate_openai_image(
                    profile,
                    prompt=clean_prompt,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                )
            else:
                raise VisionDirectorAIExecutionError(
                    f"Unsupported VisionDirector image provider: {profile.provider}"
                )

            tokens = provider_result.tokens
            return AIImageResult(
                role=profile.role or clean_provider,
                provider=profile.provider,
                model=selected_model,
                image_data_url=provider_result.image_data_url,
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



    def generate_video_for_provider(
        self,
        *,
        visual_prompt: str,
        narration_script: str = "",
        provider: str,
        aspect_ratio: str = "9:16",
        start_image_base64: str | None = None,
        voice_traits: str = "",
        prebuilt_voice: str = "Zephyr",
        speed: str = "natural",
        sentiment: str = "neutral",
        video_to_extend: Any = None,
        seconds: str = "8",
        model: str | None = None,
        operation: str = "generate_video",
    ) -> AIVideoResult:
        clean_provider = str(provider or "").strip().lower()
        profile = self.profile_registry.require_provider(clean_provider)

        selected_model = model or profile.model
        if not selected_model:
            raise VisionDirectorAIProfileError(
                f"VisionDirector host AI profile for provider '{profile.provider}' has no model."
            )

        prompt = _compose_video_prompt(
            visual_prompt=visual_prompt,
            narration_script=narration_script,
            voice_traits=voice_traits,
            prebuilt_voice=prebuilt_voice,
            speed=speed,
            sentiment=sentiment,
            start_image_base64=start_image_base64,
        )

        started_at = utc_now()
        status = "success"
        tokens = TokenBreakdown()

        try:
            if profile.provider == "google":
                provider_result = _generate_google_video(
                    profile,
                    prompt=prompt,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                    start_image_base64=start_image_base64,
                    video_to_extend=video_to_extend,
                    seconds=seconds,
                )
            elif profile.provider == "openai":
                selected_model = _smx_resolve_openai_video_model(selected_model)
                provider_result = _generate_openai_video(
                    profile,
                    prompt=prompt,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                    start_image_base64=start_image_base64,
                    video_to_extend=video_to_extend,
                    seconds=seconds,
                )
            else:
                raise VisionDirectorAIExecutionError(
                    f"Unsupported VisionDirector video provider: {profile.provider}"
                )

            tokens = provider_result.tokens
            return AIVideoResult(
                role=profile.role or clean_provider,
                provider=profile.provider,
                model=selected_model,
                video_url=provider_result.video_url,
                video_ref=provider_result.video_ref,
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

    def _generate_text_with_profile(
        self,
        *,
        profile: ProviderProfile,
        prompt: str,
        role: str,
        model: str | None = None,
        operation: str = "generate_text",
    ) -> AITextResult:
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            raise VisionDirectorAIExecutionError("prompt is required")

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
                provider_result = _generate_google_text(
                    profile,
                    prompt=clean_prompt,
                    model=selected_model,
                )
            elif profile.provider == "openai":
                provider_result = _generate_openai_text(
                    profile,
                    prompt=clean_prompt,
                    model=selected_model,
                )
            else:
                raise VisionDirectorAIExecutionError(
                    f"Unsupported VisionDirector text provider: {profile.provider}"
                )

            tokens = provider_result.tokens
            return AITextResult(
                role=role,
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
                role=role,
                provider=profile.provider,
                model=selected_model,
                status=status,
                started_at=started_at,
                tokens=tokens,
            )

    def _record_usage(
        self,
        *,
        operation: str,
        role: str | None,
        provider: str,
        model: str | None,
        status: str,
        started_at,
        tokens: TokenBreakdown,
    ) -> None:
        if self.usage_recorder is None:
            return

        self.usage_recorder.record(
            new_usage_event(
                operation=operation,
                provider=provider,
                model=model,
                role=role,
                status=status,
                started_at=started_at,
                finished_at=utc_now(),
                tokens=tokens,
            )
        )


def build_ai_runtime(
    profile_registry: AIProfileRegistry,
    *,
    usage_recorder: UsageRecorder | None = None,
) -> VisionDirectorAIRuntime:
    return VisionDirectorAIRuntime(
        profile_registry,
        usage_recorder=usage_recorder,
    )


def _generate_google_text(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
) -> _ProviderTextResponse:
    client = profile.client
    models = getattr(client, "models", None)

    if models is None or not hasattr(models, "generate_content"):
        raise VisionDirectorAIExecutionError(
            "Google host client must expose client.models.generate_content(...)."
        )

    response = models.generate_content(
        model=model,
        contents=prompt,
    )
    return _ProviderTextResponse(
        text=_extract_text(response),
        tokens=extract_token_breakdown(response),
    )


def _generate_openai_text(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
) -> _ProviderTextResponse:
    client = profile.client
    responses = getattr(client, "responses", None)

    if responses is None or not hasattr(responses, "create"):
        raise VisionDirectorAIExecutionError(
            "OpenAI host client must expose client.responses.create(...)."
        )

    response = responses.create(
        model=model,
        input=prompt,
    )
    return _ProviderTextResponse(
        text=_extract_text(response),
        tokens=extract_token_breakdown(response),
    )


def _generate_google_image(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
) -> _ProviderImageResponse:
    client = profile.client
    models = getattr(client, "models", None)

    if models is None or not hasattr(models, "generate_content"):
        raise VisionDirectorAIExecutionError(
            "Google host client must expose client.models.generate_content(...)."
        )

    response = models.generate_content(
        model=model,
        contents={
            "parts": [
                {
                    "text": (
                        "High-fidelity cinematic production keyframe: "
                        f"{prompt}. Photo-realistic lighting."
                    )
                }
            ]
        },
        config={"imageConfig": {"aspectRatio": aspect_ratio}},
    )

    b64 = _extract_inline_image_b64(response)
    return _ProviderImageResponse(
        image_data_url=f"data:image/png;base64,{b64}" if b64 else None,
        tokens=extract_token_breakdown(response),
    )


def _generate_openai_image(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
) -> _ProviderImageResponse:
    client = profile.client
    images = getattr(client, "images", None)

    if images is None or not hasattr(images, "generate"):
        raise VisionDirectorAIExecutionError(
            "OpenAI host client must expose client.images.generate(...)."
        )

    response = images.generate(
        model=model,
        prompt=prompt,
        size=_aspect_ratio_to_openai_size(aspect_ratio),
        n=1,
        output_format="png",
        quality="auto",
        background="auto",
    )

    b64 = _extract_openai_image_b64(response)
    return _ProviderImageResponse(
        image_data_url=f"data:image/png;base64,{b64}" if b64 else None,
        tokens=extract_token_breakdown(response),
    )


def _aspect_ratio_to_openai_size(aspect_ratio: str) -> str:
    if aspect_ratio == "16:9":
        return "1536x1024"
    if aspect_ratio == "9:16":
        return "1024x1536"
    return "1024x1024"


def _extract_text(response: Any) -> str:
    direct = getattr(response, "text", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    if isinstance(response, dict):
        for key in ("text", "output_text"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    raise VisionDirectorAIExecutionError("AI response did not contain text output.")


def _extract_inline_image_b64(response: Any) -> str | None:
    candidates = _get_value(response, "candidates") or []
    for candidate in candidates:
        content = _get_value(candidate, "content") or {}
        parts = _get_value(content, "parts") or []
        for part in parts:
            inline_data = _get_value(part, "inlineData") or _get_value(part, "inline_data")
            if inline_data:
                data = _get_value(inline_data, "data")
                if isinstance(data, str) and data.strip():
                    return data.strip()
    return None


def _extract_openai_image_b64(response: Any) -> str | None:
    data_items = _get_value(response, "data") or []
    if not data_items:
        return None

    first = data_items[0]
    b64 = _get_value(first, "b64_json")
    if isinstance(b64, str) and b64.strip():
        return b64.strip()

    return None


def _get_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
def _compose_video_prompt(
    *,
    visual_prompt: str,
    narration_script: str = "",
    voice_traits: str = "",
    prebuilt_voice: str = "Zephyr",
    speed: str = "natural",
    sentiment: str = "neutral",
    start_image_base64: str | None = None,
) -> str:
    clean_visuals = _clean_video_text(visual_prompt, 1800) or "Cinematic sequence"
    clean_narration = _clean_video_text(narration_script, 1600)
    clean_traits = _clean_video_text(voice_traits, 1200)
    clean_voice = _clean_video_text(prebuilt_voice or "Zephyr", 80)
    clean_speed = _clean_video_text(speed or "natural", 80)
    clean_sentiment = _clean_video_text(sentiment or "neutral", 80)

    speaker_lock = ""
    if start_image_base64 and clean_narration:
        speaker_lock = "\n".join(
            [
                "[REFERENCE SPEAKER LOCK - HIGHEST PRIORITY]",
                "- The supplied reference image is the exact on-screen speaker.",
                "- Keep identity, face, skin tone, hair, age, clothing, and framing faithful to the reference image.",
                "- Animate natural lip movement and facial performance tightly synced to the narration.",
                "- Do not introduce another speaker.",
            ]
        )

    voice_block = "\n".join(
        [
            "[VOICE_PROFILE]",
            f"base_voice: {clean_voice}",
            f"speed: {clean_speed}",
            f"sentiment: {clean_sentiment}",
            clean_traits and "[VOICE_RESEMBLANCE_DNA]",
            clean_traits,
        ]
    ).strip()

    narration_block = (
        "\n".join(
            [
                "[AUDIO_DIRECTION]",
                "Use synchronized spoken narration.",
                voice_block,
                "",
                "[NARRATION_TEXT - READ VERBATIM]",
                clean_narration,
            ]
        )
        if clean_narration
        else "Ambient cinematic audio with zero narration."
    )

    return "\n\n".join(
        part
        for part in [
            speaker_lock,
            f"[TEMPORAL CONSISTENCY RIGOROUS] {clean_visuals}",
            narration_block,
        ]
        if part
    ).strip()


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
        text = "\n".join(fragments)

    return _ProviderTextResponse(
        text=str(text or "").strip(),
        tokens=extract_token_breakdown(response),
    )



def _generate_google_video(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
    start_image_base64: str | None,
    video_to_extend: Any,
    seconds: str,
) -> _ProviderVideoResponse:
    client = profile.client
    models = getattr(client, "models", None)
    if models is None:
        raise VisionDirectorAIExecutionError("Google host client has no models interface.")

    generate = getattr(models, "generate_videos", None) or getattr(models, "generateVideos", None)
    if generate is None:
        raise VisionDirectorAIExecutionError("Google host client does not support video generation.")

    clean_start = _strip_data_url_prefix(start_image_base64)
    config = {
        "numberOfVideos": 1,
        "resolution": "720p",
    }
    if not video_to_extend:
        config["aspectRatio"] = "9:16" if str(aspect_ratio) == "9:16" else "16:9"

    kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "config": config,
    }

    if video_to_extend:
        google_video_input = _coerce_google_video_extension_input(video_to_extend)
        if google_video_input is not None:
            kwargs["video"] = google_video_input
        kwargs["prompt"] = (
            "[DIRECTOR_EXTENSION_REQUEST]\n"
            f"{prompt}\n\n"
            "[EXTENSION]\n"
            "This is a continuation of the previous clip. Ensure identical visual subjects and motion continuity."
        )
    elif clean_start:
        kwargs["image"] = {"imageBytes": clean_start, "mimeType": "image/png"}

    try:
        operation = generate(**kwargs)
    except Exception as exc:
        raise VisionDirectorAIExecutionError(str(exc)) from exc
    operation = _poll_google_video_operation(client, operation)

    error = _get_value(operation, "error")
    if error:
        message = _get_value(error, "message") or str(error)
        raise VisionDirectorAIExecutionError(str(message))

    video = _extract_google_video_object(operation)
    if video is None:
        raise VisionDirectorAIExecutionError("Google video response did not include a video object.")

    video_url = _extract_google_video_url(profile, video)
    if not video_url:
        raise VisionDirectorAIExecutionError("Google video response did not include downloadable video content.")

    return _ProviderVideoResponse(
        video_url=video_url,
        video_ref=_google_video_ref_for_extension(video=video, video_url=video_url),
        tokens=extract_token_breakdown(operation),
    )


def _google_video_ref_for_extension(*, video: Any, video_url: str | None) -> Any:
    handle = _new_google_video_extension_handle(video)
    mime_type = (
        _get_value(video, "mimeType")
        or _get_value(video, "mime_type")
        or "video/mp4"
    )

    ref: dict[str, Any] = {
        "provider": "google",
        "extensionHandle": handle,
        "mimeType": str(mime_type),
        "source": "veo_generated_video_object",
    }

    name = _get_value(video, "name")
    video_id = _get_value(video, "id")
    if name:
        ref["name"] = str(name)
    if video_id:
        ref["id"] = str(video_id)

    return ref



def _coerce_google_video_extension_input(video_to_extend: Any) -> Any:
    handle = _extract_google_video_extension_handle(video_to_extend)
    if handle:
        video = _GOOGLE_VIDEO_EXTENSION_HANDLES.get(handle)
        if video is None:
            raise VisionDirectorAIExecutionError(
                "GOOGLE_EXTENSION_HANDLE_EXPIRED: generate a fresh Google video in this running server session, then extend it before restarting."
            )
        return video

    if video_to_extend and not isinstance(video_to_extend, (dict, str)):
        return video_to_extend

    raise VisionDirectorAIExecutionError(
        "GOOGLE_EXTENSION_REQUIRES_VEO_VIDEO_OBJECT: Google Veo extension requires the previous generated video object from the same running server session."
    )





def _smx_store_openai_video_extension_bytes(
    video_bytes: bytes | bytearray | None,
    *,
    provider_video_id: str | None = None,
) -> dict[str, str] | None:
    data = bytes(video_bytes or b"")
    if not data:
        return None

    handle = f"openai-ext-{len(_OPENAI_VIDEO_EXTENSION_HANDLES) + 1}"
    _OPENAI_VIDEO_EXTENSION_HANDLES[handle] = data

    ref = {"openaiExtensionHandle": handle}
    if provider_video_id:
        _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[handle] = str(provider_video_id)
        ref["providerVideoId"] = str(provider_video_id)
    return ref


def _smx_resolve_openai_video_extension_bytes(video_to_extend: Any) -> bytes:
    if isinstance(video_to_extend, (bytes, bytearray)):
        return bytes(video_to_extend)

    handle = None
    if isinstance(video_to_extend, dict):
        for key in (
            "openaiExtensionHandle",
            "extensionHandle",
            "handle",
            "videoRef",
        ):
            value = video_to_extend.get(key)
            if value:
                handle = str(value)
                break
    else:
        value = str(video_to_extend or "").strip()
        if value:
            handle = value

    if handle and handle in _OPENAI_VIDEO_EXTENSION_HANDLES:
        return _OPENAI_VIDEO_EXTENSION_HANDLES[handle]

    raise VisionDirectorAIExecutionError(
        "OPENAI_VIDEO_EXTENSION_REQUIRES_VIDEO_BYTES: generate a fresh OpenAI video in this running server session, then extend it before restarting."
    )


def _smx_openai_extend_video_reference(video_to_extend: Any) -> bytes:
    """
    The installed OpenAI Python SDK treats videos.extend(video=...) as a file
    upload parameter. Therefore the value passed to `video` must be bytes,
    IO, PathLike, or a file tuple, not a provider video id object.
    """
    return _smx_resolve_openai_video_extension_bytes(video_to_extend)


def _smx_openai_extension_video_id(video_to_extend: Any) -> str:
    """
    Resolve the OpenAI provider video id required by the official
    /videos/extensions JSON endpoint.

    Local handles such as openai-ext-1 are only valid if they were mapped
    to the original provider video id when the video was generated.
    """
    if isinstance(video_to_extend, dict):
        handle = (
            video_to_extend.get("openaiExtensionHandle")
            or video_to_extend.get("extensionHandle")
            or video_to_extend.get("handle")
            or video_to_extend.get("videoRef")
        )
        if handle:
            handle_key = str(handle)
            if handle_key in _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS:
                return _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[handle_key]

        for key in ("providerVideoId", "provider_video_id", "video_id", "id"):
            value = video_to_extend.get(key)
            if value:
                return str(value)

        raise VisionDirectorAIExecutionError(
            "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"
        )

    for attr in ("providerVideoId", "provider_video_id", "video_id", "id"):
        value = getattr(video_to_extend, attr, None)
        if value:
            return str(value)

    value = str(video_to_extend or "").strip()
    if value in _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS:
        return _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[value]

    if value and not value.startswith("openai-ext-"):
        return value

    raise VisionDirectorAIExecutionError(
        "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"
    )

def _smx_openai_api_key(profile: ProviderProfile, client: Any) -> str:
    value = getattr(client, "api_key", None) or getattr(profile, "api_key", None)
    token = str(value or "").strip()
    if not token:
        raise VisionDirectorAIExecutionError(
            "OPENAI_API_KEY_MISSING_FOR_VIDEO_EXTENSION"
        )
    return token


def _smx_openai_base_url(client: Any) -> str:
    value = str(getattr(client, "base_url", "") or OPENAI_DEFAULT_BASE_URL).strip()
    if not value or "://" not in value:
        value = OPENAI_DEFAULT_BASE_URL
    return value.rstrip("/")


def _smx_openai_extend_video_via_json_endpoint(
    client: Any,
    *,
    profile: ProviderProfile,
    prompt: str,
    seconds: str,
    video_to_extend: Any,
) -> Any:
    """
    Use the official OpenAI HTTP JSON extension endpoint.

    The installed Python SDK currently serializes videos.extend(video=...)
    inconsistently for our use case, while the official HTTP API expects:
      POST /videos/extensions
      {"prompt": "...", "seconds": "4", "video": {"id": "video_123"}}
    """
    video_id = _smx_openai_extension_video_id(video_to_extend)
    api_key = _smx_openai_api_key(profile, client)
    url = _smx_openai_base_url(client) + "/videos/extensions"

    body = json.dumps(
        {
            "prompt": prompt,
            "seconds": str(seconds or "8"),
            "video": {"id": video_id},
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VisionDirectorAIExecutionError(
            f"OPENAI_VIDEO_EXTENSION_FAILED: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise VisionDirectorAIExecutionError(
            f"OPENAI_VIDEO_EXTENSION_REQUEST_FAILED: {exc}"
        ) from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise VisionDirectorAIExecutionError(
            "OPENAI_VIDEO_EXTENSION_RETURNED_INVALID_JSON"
        ) from exc



def _smx_openai_input_reference_json(start_image_base64: str | None) -> dict[str, str] | None:
    raw = str(start_image_base64 or "").strip()
    if not raw:
        return None

    if raw.startswith("http://") or raw.startswith("https://"):
        return {"image_url": raw}

    if raw.startswith("data:image/"):
        return {"image_url": raw}

    if "base64," in raw:
        return {"image_url": raw}

    return {"image_url": "data:image/png;base64," + raw}


def _smx_openai_create_video_via_json_endpoint(
    client: Any,
    *,
    profile: ProviderProfile,
    model: str,
    prompt: str,
    seconds: str,
    size: str,
    start_image_base64: str | None,
) -> Any:
    """
    Use the official OpenAI JSON video-create endpoint when a reference
    image is present.

    The OpenAI API accepts:
      {"input_reference": {"image_url": "data:image/png;base64,..."}}
    but the installed Python SDK path has treated input_reference
    inconsistently. Raw JSON keeps VisionDirector aligned with the
    official API contract.
    """
    api_key = _smx_openai_api_key(profile, client)
    url = _smx_openai_base_url(client) + "/videos"

    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "seconds": str(seconds or "8"),
        "size": size,
    }

    reference = _smx_openai_input_reference_json(start_image_base64)
    if reference:
        body["input_reference"] = reference

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VisionDirectorAIExecutionError(
            f"OPENAI_VIDEO_CREATE_FAILED: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise VisionDirectorAIExecutionError(
            f"OPENAI_VIDEO_CREATE_REQUEST_FAILED: {exc}"
        ) from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise VisionDirectorAIExecutionError(
            "OPENAI_VIDEO_CREATE_RETURNED_INVALID_JSON"
        ) from exc


def _generate_openai_video(
    profile: ProviderProfile,
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
    start_image_base64: str | None,
    video_to_extend: Any,
    seconds: str,
) -> _ProviderVideoResponse:
    client = profile.client
    _smx_ensure_openai_client_base_url(client)

    videos = getattr(client, "videos", None)
    if videos is None:
        raise VisionDirectorAIExecutionError("OpenAI host client has no videos interface.")

    size = _aspect_ratio_to_openai_video_size(aspect_ratio)
    create = getattr(videos, "create", None)

    if video_to_extend:
        job = _smx_openai_extend_video_via_json_endpoint(
            client,
            profile=profile,
            prompt=prompt,
            seconds=str(seconds or "8"),
            video_to_extend=video_to_extend,
        )
    elif start_image_base64:
        job = _smx_openai_create_video_via_json_endpoint(
            client,
            profile=profile,
            model=model,
            prompt=prompt,
            seconds=str(seconds or "8"),
            size=size,
            start_image_base64=start_image_base64,
        )
    elif create is not None:
        job = create(
            model=model,
            prompt=prompt,
            seconds=str(seconds or "8"),
            size=size,
        )
    else:
        raise VisionDirectorAIExecutionError(
            "OpenAI host client does not support video generation."
        )

    done = _poll_openai_video(client, job)
    video_id = _get_value(done, "id") or _get_value(job, "id")
    video_url = _download_openai_video_data_url(client, video_id)

    if not video_url:
        direct_url = _get_value(done, "url") or _get_value(done, "content_url")
        video_url = str(direct_url) if direct_url else None

    if not video_url:
        raise VisionDirectorAIExecutionError(
            "OpenAI video response did not include downloadable video content."
        )

    openai_video_bytes = _decode_data_url_bytes(video_url)
    openai_extension_ref = _smx_store_openai_video_extension_bytes(
        openai_video_bytes,
        provider_video_id=str(video_id or "") or None,
    )

    return _ProviderVideoResponse(
        video_url=video_url,
        video_ref=openai_extension_ref or str(video_id or ""),
        tokens=extract_token_breakdown(done),
    )

def _poll_google_video_operation(client: Any, operation: Any) -> Any:
    for _ in range(90):
        if bool(_get_value(operation, "done")):
            return operation

        operations = getattr(client, "operations", None)
        getter = None
        if operations is not None:
            getter = (
                getattr(operations, "get", None)
                or getattr(operations, "get_videos_operation", None)
                or getattr(operations, "getVideosOperation", None)
            )

        if getter is None:
            return operation

        try:
            operation = getter(operation)
        except TypeError:
            operation = getter(operation=operation)

        if bool(_get_value(operation, "done")):
            return operation

        time.sleep(8)

    return operation
def _poll_openai_video(client: Any, job: Any) -> Any:
    status = str(_get_value(job, "status") or "").lower()
    if status in {"completed", "succeeded", "done"}:
        return job

    video_id = _get_value(job, "id")
    if not video_id:
        return job

    videos = getattr(client, "videos", None)
    retrieve = getattr(videos, "retrieve", None) or getattr(videos, "get", None)

    if retrieve is None:
        return job

    latest = job
    for _ in range(90):
        latest = retrieve(video_id)
        status = str(_get_value(latest, "status") or "").lower()
        if status in {"completed", "succeeded", "done"}:
            return latest
        if status in {"failed", "cancelled", "canceled"}:
            message = _get_value(_get_value(latest, "error"), "message") or "OpenAI video generation failed."
            raise VisionDirectorAIExecutionError(str(message))
        time.sleep(2)

    raise VisionDirectorAIExecutionError("OpenAI video generation timed out.")


def _extract_google_video_object(operation: Any) -> Any:
    containers = [
        _get_value(operation, "response"),
        _get_value(operation, "result"),
        operation,
    ]

    for container in containers:
        if not container:
            continue

        generated = (
            _get_value(container, "generatedVideos")
            or _get_value(container, "generated_videos")
            or _get_value(container, "generatedvideos")
            or []
        )

        if generated and isinstance(generated, (list, tuple)):
            first = generated[0]
            return _get_value(first, "video") or first

        direct_video = _get_value(container, "video")
        if direct_video:
            return direct_video

    return None
def _extract_google_video_url(profile: ProviderProfile, video: Any) -> str | None:
    direct = _get_value(video, "url") or _get_value(video, "dataUrl") or _get_value(video, "data_url")
    if direct:
        return str(direct)

    raw_b64 = (
        _get_value(video, "data")
        or _get_value(video, "videoBytes")
        or _get_value(video, "video_bytes")
        or _get_value(video, "bytes")
    )
    if raw_b64:
        if isinstance(raw_b64, bytes):
            raw_b64 = base64.b64encode(raw_b64).decode("ascii")
        return f"data:video/mp4;base64,{raw_b64}"

    downloaded = _download_google_video_bytes_with_client(profile.client, video)
    if downloaded:
        return "data:video/mp4;base64," + base64.b64encode(downloaded).decode("ascii")

    uri = _get_value(video, "uri")
    if not uri:
        return None

    raw_key = str(getattr(profile, "api_key", "") or "").strip()
    if raw_key:
        separator = "&" if "?" in str(uri) else "?"
        download_url = f"{uri}{separator}key={raw_key}"
        try:
            req = urlrequest.Request(download_url, headers={"User-Agent": "smx-visiondirector"})
            with urlrequest.urlopen(req, timeout=120) as response:
                data = response.read()
            return "data:video/mp4;base64," + base64.b64encode(data).decode("ascii")
        except Exception:
            pass

    return str(uri)


def _download_google_video_bytes_with_client(client: Any, video: Any) -> bytes | None:
    files = getattr(client, "files", None)
    download = getattr(files, "download", None) if files is not None else None

    candidates = [
        video,
        _get_value(video, "name"),
        _get_value(video, "uri"),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        if download is not None:
            try:
                result = download(file=candidate)
            except TypeError:
                try:
                    result = download(candidate)
                except Exception:
                    result = None
            except Exception:
                result = None

            for value in (result, candidate):
                data = _bytes_from_possible_response(value)
                if data:
                    return data

                data = _bytes_from_google_file_save(value)
                if data:
                    return data

        for value in (candidate,):
            data = _bytes_from_possible_response(value)
            if data:
                return data

            data = _bytes_from_google_file_save(value)
            if data:
                return data

    return None


def _bytes_from_google_file_save(file_obj: Any) -> bytes | None:
    save = getattr(file_obj, "save", None)
    if save is None or not callable(save):
        return None

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            temp_path = Path(tmp.name)

        result = save(str(temp_path))

        data = _bytes_from_possible_response(result)
        if data:
            return data

        if temp_path.exists():
            data = temp_path.read_bytes()
            if data:
                return data
    except Exception:
        return None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass

    return None


def _download_openai_video_data_url(client: Any, video_id: Any) -> str | None:
    if not video_id:
        return None

    videos = getattr(client, "videos", None)
    for method_name in ("content", "retrieve_content", "download_content"):
        method = getattr(videos, method_name, None) if videos is not None else None
        if method is None:
            continue
        try:
            result = method(video_id)
            data = _bytes_from_possible_response(result)
            if data:
                return "data:video/mp4;base64," + base64.b64encode(data).decode("ascii")
        except Exception:
            continue

    return None


def _bytes_from_possible_response(value: Any) -> bytes | None:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if hasattr(value, "read"):
        data = value.read()
        return data if isinstance(data, bytes) else None
    content = _get_value(value, "content")
    if isinstance(content, bytes):
        return content
    data = _get_value(value, "data")
    if isinstance(data, bytes):
        return data
    return None


def _strip_data_url_prefix(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value)
    if "base64," in raw:
        return raw.split("base64,", 1)[1]
    return raw


def _decode_data_url_bytes(value: str | None) -> bytes | None:
    raw = _strip_data_url_prefix(value)
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except Exception:
        return None


def _clean_video_text(value: Any, max_len: int) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").strip()
    text = " ".join(text.split())
    if len(text) > max_len:
        text = text[:max_len].strip()
    return text


def _aspect_ratio_to_openai_video_size(aspect_ratio: str) -> str:
    return "720x1280" if str(aspect_ratio) == "9:16" else "1280x720"


def _json_safe_video_ref(video: Any) -> Any:
    if isinstance(video, (str, int, float, bool)) or video is None:
        return video

    if isinstance(video, dict):
        safe = {}
        for key, value in video.items():
            if key in {"data", "videoBytes", "video_bytes", "bytes"}:
                continue
            safe[str(key)] = _json_safe_video_ref(value)
        return safe

    uri = _get_value(video, "uri")
    name = _get_value(video, "name")
    video_id = _get_value(video, "id")
    mime_type = _get_value(video, "mimeType") or _get_value(video, "mime_type") or "video/mp4"

    if uri or name or video_id:
        safe: dict[str, Any] = {}
        if uri:
            safe["uri"] = str(uri)
        if name:
            safe["name"] = str(name)
        if video_id:
            safe["id"] = str(video_id)
        if mime_type:
            safe["mimeType"] = str(mime_type)
        return safe

    return ""


# smx-visiondirector audio runtime method bindings


def _smx_record_usage_if_available(runtime: Any, **kwargs: Any) -> None:
    record_usage = getattr(runtime, "_record_usage", None)
    if callable(record_usage):
        record_usage(**kwargs)
        return

    # Some migration states do not expose _record_usage as a method.
    # In that case, do not fail the user-facing audio request.
    return

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
        _smx_record_usage_if_available(
            self,
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
                    f"Sentiment: {sentiment}\n"
                    f"Transcript:\n{transcript_result.text}\n\n"
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
        _smx_record_usage_if_available(
            self,
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


# smx-visiondirector provider-backed TTS preview bindings


GOOGLE_TTS_PREVIEW_MODEL = "gemini-3.1-flash-tts-preview"
OPENAI_TTS_PREVIEW_MODEL = "gpt-4o-mini-tts"
OPENAI_VIDEO_DEFAULT_MODEL = "sora-2"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _smx_is_google_tts_model(model: str | None) -> bool:
    return "tts" in str(model or "").strip().lower()


def _smx_resolve_google_tts_model(model: str | None) -> str:
    if _smx_is_google_tts_model(model):
        return str(model).strip()
    return GOOGLE_TTS_PREVIEW_MODEL


def _smx_is_openai_tts_model(model: str | None) -> bool:
    value = str(model or "").strip().lower()
    return (
        value == "gpt-4o-mini-tts"
        or value.startswith("gpt-4o-mini-tts-")
        or value in {"tts-1", "tts-1-hd"}
    )


def _smx_resolve_openai_tts_model(model: str | None) -> str:
    if _smx_is_openai_tts_model(model):
        return str(model).strip()
    return OPENAI_TTS_PREVIEW_MODEL


def _smx_ensure_openai_client_base_url(client: Any) -> None:
    """
    OpenAI provider profiles should use an absolute OpenAI API base URL.

    Some host/sandbox clients can accidentally carry a relative base URL such
    as "/v1", which later fails as: Invalid URL (POST /v1/audio/speech).
    This does not instantiate a new model/client; it only normalizes the
    host-provided OpenAI client when its base URL is clearly invalid.
    """
    if client is None:
        return

    current = ""
    try:
        current = str(getattr(client, "base_url", "") or "").strip()
    except Exception:
        current = ""

    if current and "://" in current:
        return

    try:
        setattr(client, "base_url", OPENAI_DEFAULT_BASE_URL)
    except Exception:
        pass


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


def _smx_audio_bytes_from_inline_data(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)

    if isinstance(data, str):
        raw = data.strip()
        if raw.startswith("data:") and "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            return base64.b64decode(raw)
        except Exception as exc:
            raise VisionDirectorAIExecutionError("TTS_PREVIEW_INVALID_AUDIO_BASE64") from exc

    raise VisionDirectorAIExecutionError("TTS_PREVIEW_UNSUPPORTED_AUDIO_DATA")


def _smx_audio_sample_rate_from_mime(mime_type: str | None) -> int:
    text = str(mime_type or "").lower()
    for token in text.replace(";", " ").replace(",", " ").split():
        if token.startswith("rate="):
            try:
                return int(token.split("=", 1)[1])
            except Exception:
                pass
    return 24000


def _smx_wav_bytes_from_pcm(
    pcm: bytes,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    if pcm.startswith(b"RIFF") and b"WAVE" in pcm[:16]:
        return pcm

    bits_per_sample = sample_width * 8
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    data_size = len(pcm)
    riff_size = 36 + data_size

    header = b"".join(
        [
            b"RIFF",
            riff_size.to_bytes(4, "little"),
            b"WAVE",
            b"fmt ",
            (16).to_bytes(4, "little"),
            (1).to_bytes(2, "little"),
            channels.to_bytes(2, "little"),
            sample_rate.to_bytes(4, "little"),
            byte_rate.to_bytes(4, "little"),
            block_align.to_bytes(2, "little"),
            bits_per_sample.to_bytes(2, "little"),
            b"data",
            data_size.to_bytes(4, "little"),
        ]
    )
    return header + pcm


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
            if data is None:
                continue

            mime_type = (
                _get_value(inline, "mime_type")
                or _get_value(inline, "mimeType")
                or "audio/pcm;rate=24000"
            )

            pcm_or_wav = _smx_audio_bytes_from_inline_data(data)
            sample_rate = _smx_audio_sample_rate_from_mime(str(mime_type))
            wav_bytes = _smx_wav_bytes_from_pcm(
                pcm_or_wav,
                sample_rate=sample_rate,
                channels=1,
                sample_width=2,
            )
            wav_b64 = base64.b64encode(wav_bytes).decode("ascii")
            return f"data:audio/wav;base64,{wav_b64}"

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
    _smx_ensure_openai_client_base_url(client)
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
            selected_model = _smx_resolve_google_tts_model(selected_model)
            audio_url = _smx_google_voice_preview(
                profile,
                model=selected_model,
                voice=voice,
                speed=speed,
                traits=traits,
                text=text,
            )
        elif profile.provider == "openai":
            selected_model = _smx_resolve_openai_tts_model(selected_model)
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


def _smx_is_openai_video_model(model: str | None) -> bool:
    value = str(model or "").strip().lower()
    return value in {
        "sora-2",
        "sora-2-pro",
        "sora-2-2025-10-06",
        "sora-2-pro-2025-10-06",
        "sora-2-2025-12-08",
    }


def _smx_resolve_openai_video_model(model: str | None) -> str:
    if _smx_is_openai_video_model(model):
        return str(model).strip()
    return OPENAI_VIDEO_DEFAULT_MODEL


def _smx_openai_input_reference(start_image_base64: str | None) -> bytes | None:
    """
    OpenAI Python SDK videos.create() expects input_reference to be
    uploadable file content: bytes, IO, PathLike, or a file tuple.

    The browser sends the reference image as a data URL or raw base64 string,
    so VisionDirector must decode it to bytes before passing it to OpenAI.
    """
    raw = str(start_image_base64 or "").strip()
    if not raw:
        return None

    if raw.startswith("http://") or raw.startswith("https://"):
        raise VisionDirectorAIExecutionError(
            "OPENAI_VIDEO_INPUT_REFERENCE_URL_UNSUPPORTED"
        )

    data = _decode_data_url_bytes(raw)
    if data:
        return data

    raise VisionDirectorAIExecutionError(
        "OPENAI_VIDEO_INPUT_REFERENCE_INVALID_BASE64"
    )

