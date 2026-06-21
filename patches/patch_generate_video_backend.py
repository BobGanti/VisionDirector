from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not runtime_file.exists() or not init_file.exists():
    raise SystemExit("Run from VisionDirector root.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


runtime = runtime_file.read_text(encoding="utf-8")

if "import base64\n" not in runtime:
    runtime = runtime.replace(
        "from dataclasses import dataclass\n",
        "import base64\n"
        "import time\n"
        "from urllib import request as urlrequest\n\n"
        "from dataclasses import dataclass\n",
        1,
    )

if "class AIVideoResult:" not in runtime:
    marker = '''@dataclass(frozen=True)
class _ProviderTextResponse:
'''
    insert = '''@dataclass(frozen=True)
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


'''
    if marker not in runtime:
        raise SystemExit("Could not find provider text response marker.")
    runtime = runtime.replace(marker, insert + marker, 1)

if "def generate_video_for_provider(" not in runtime:
    marker = '''    def _generate_text_with_profile(
'''
    method = '''    def generate_video_for_provider(
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

'''
    if marker not in runtime:
        raise SystemExit("Could not find _generate_text_with_profile marker.")
    runtime = runtime.replace(marker, method + marker, 1)

if "def _compose_video_prompt(" not in runtime:
    runtime += dedent(
        r'''

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
                "aspectRatio": "9:16" if str(aspect_ratio) == "9:16" else "16:9",
            }

            kwargs: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "config": config,
            }

            if video_to_extend:
                kwargs["video"] = video_to_extend
                kwargs["prompt"] = (
                    "[DIRECTOR_EXTENSION_REQUEST]\n"
                    f"{prompt}\n\n"
                    "[EXTENSION]\n"
                    "This is a continuation of the previous clip. Ensure identical visual subjects and motion continuity."
                )
            elif clean_start:
                kwargs["image"] = {"imageBytes": clean_start, "mimeType": "image/png"}

            operation = generate(**kwargs)
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
                video_ref=_json_safe_video_ref(video),
                tokens=extract_token_breakdown(operation),
            )


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
            videos = getattr(client, "videos", None)
            if videos is None:
                raise VisionDirectorAIExecutionError("OpenAI host client has no videos interface.")

            size = _aspect_ratio_to_openai_video_size(aspect_ratio)
            create = getattr(videos, "create", None)
            remix = getattr(videos, "remix", None)

            if video_to_extend and remix is not None:
                job = remix(
                    video=video_to_extend,
                    model=model,
                    prompt=prompt,
                    seconds=str(seconds or "8"),
                    size=size,
                )
            elif create is not None:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "prompt": prompt,
                    "seconds": str(seconds or "8"),
                    "size": size,
                }
                ref_bytes = _decode_data_url_bytes(start_image_base64)
                if ref_bytes:
                    kwargs["input_reference"] = ref_bytes
                job = create(**kwargs)
            else:
                raise VisionDirectorAIExecutionError("OpenAI host client does not support video generation.")

            done = _poll_openai_video(client, job)
            video_id = _get_value(done, "id") or _get_value(job, "id")
            video_url = _download_openai_video_data_url(client, video_id)

            if not video_url:
                direct_url = _get_value(done, "url") or _get_value(done, "content_url")
                video_url = str(direct_url) if direct_url else None

            if not video_url:
                raise VisionDirectorAIExecutionError("OpenAI video response did not include downloadable video content.")

            return _ProviderVideoResponse(
                video_url=video_url,
                video_ref=str(video_id or ""),
                tokens=extract_token_breakdown(done),
            )


        def _poll_google_video_operation(client: Any, operation: Any) -> Any:
            for _ in range(90):
                if bool(_get_value(operation, "done")):
                    return operation

                operations = getattr(client, "operations", None)
                getter = None
                if operations is not None:
                    getter = getattr(operations, "get_videos_operation", None) or getattr(operations, "getVideosOperation", None)

                if getter is None:
                    return operation

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
            response = _get_value(operation, "response")
            generated = (
                _get_value(response, "generatedVideos")
                or _get_value(response, "generated_videos")
                or _get_value(response, "generatedvideos")
                or []
            )

            if generated and isinstance(generated, list):
                return _get_value(generated[0], "video") or generated[0]

            return _get_value(response, "video")


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
            if download is None:
                return None

            candidates = [
                {"file": video},
                {"file": _get_value(video, "name")},
                {"name": _get_value(video, "name")},
            ]

            for kwargs in candidates:
                if not all(kwargs.values()):
                    continue
                try:
                    result = download(**kwargs)
                    if isinstance(result, bytes):
                        return result
                    if hasattr(result, "read"):
                        return result.read()
                    content = _get_value(result, "content")
                    if isinstance(content, bytes):
                        return content
                except Exception:
                    continue

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
                    if key in {"uri", "url", "data", "videoBytes", "video_bytes", "bytes"}:
                        continue
                    safe[str(key)] = _json_safe_video_ref(value)
                return safe
            name = _get_value(video, "name") or _get_value(video, "id") or _get_value(video, "uri")
            return str(name or "")
        '''
    ).lstrip()

runtime_file.write_text(runtime, encoding="utf-8")
print("updated ai_runtime.py with host-backed video generation")

init = init_file.read_text(encoding="utf-8")

if '@bp.post("/api/ai/generate-video")' not in init:
    marker = '    @bp.get("/api/usage/report")\n'
    if marker not in init:
        raise SystemExit("Could not find usage report marker for route insertion.")

    route = '''    @bp.post("/api/ai/generate-video")
    def ai_generate_video():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or settings_store["supplier"]).strip().lower()
        visual_prompt = str(payload.get("visualPrompt") or "").strip()
        narration_script = str(payload.get("narrationScript") or "")
        aspect_ratio = str(payload.get("aspectRatio") or "9:16").strip()
        start_image_base64 = payload.get("startImageBase64")
        voice_traits = str(payload.get("voiceTraits") or "")
        prebuilt_voice = str(payload.get("prebuiltVoice") or "Zephyr")
        speed = str(payload.get("speed") or "natural")
        sentiment = str(payload.get("sentiment") or "neutral")
        video_to_extend = payload.get("videoToExtend")
        seconds = str(payload.get("seconds") or "8")
        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("VIDEO_GEN", supplier)
        )

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        try:
            result = build_ai_runtime(
                profile_registry,
                usage_recorder=resolved_usage_recorder,
            ).generate_video_for_provider(
                operation="generate_video",
                provider=supplier,
                visual_prompt=visual_prompt,
                narration_script=narration_script,
                aspect_ratio=aspect_ratio,
                start_image_base64=start_image_base64,
                voice_traits=voice_traits,
                prebuilt_voice=prebuilt_voice,
                speed=speed,
                sentiment=sentiment,
                video_to_extend=video_to_extend,
                seconds=seconds,
                model=model,
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "url": result.video_url,
            "videoRef": result.video_ref,
            "supplier": result.provider,
            "model": result.model,
        }


'''
    init = init.replace(marker, route + marker, 1)

old_function_end = '''  return data?.imageDataUrl || null;
}
'''
new_function_end = '''  return data?.imageDataUrl || null;
}

async function __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, supplier) {
  const res = await fetch("/visiondirector/api/ai/generate-video", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      supplier,
      visualPrompt,
      narrationScript,
      aspectRatio,
      startImageBase64,
      voiceTraits,
      prebuiltVoice,
      speed,
      sentiment,
      videoToExtend,
      seconds
    })
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(data?.error || `VISIONDIRECTOR_GENERATE_VIDEO_FAILED: ${res.status}`);
  }
  return { url: data?.url || "", videoRef: data?.videoRef || null };
}
'''

if "__smxVisionDirectorGenerateVideo" not in init:
    if old_function_end not in init:
        raise SystemExit("Could not find runtime image helper end.")
    init = init.replace(old_function_end, new_function_end, 1)

google_line = '    googleProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "google");'
google_video_line = '    googleProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, "google");'

if google_video_line not in init:
    init = init.replace(google_line, google_line + '\\n' + google_video_line, 1)

openai_line = '    openaiProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "openai");'
openai_video_line = '    openaiProvider.generateVideo = (visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds) => __smxVisionDirectorGenerateVideo(visualPrompt, narrationScript, aspectRatio, startImageBase64, voiceTraits, prebuiltVoice, speed, sentiment, videoToExtend, seconds, "openai");'

if openai_video_line not in init:
    init = init.replace(openai_line, openai_line + '\\n' + openai_video_line, 1)

init_file.write_text(init, encoding="utf-8")
print("updated __init__.py with generate-video route and runtime JS override")

write_file(
    "tests/test_ai_generate_video_route.py",
    """
    from __future__ import annotations

    import base64

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeGoogleModels:
        def __init__(self):
            self.calls = []

        def generate_videos(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "done": True,
                "response": {
                    "generatedVideos": [
                        {
                            "video": {
                                "uri": "data:video/mp4;base64,GOOGLE_VIDEO_B64",
                                "name": "google-video-1",
                            }
                        }
                    ]
                },
            }


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    class FakeOpenAIVideos:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return {"id": "openai-video-1", "status": "completed"}

        def content(self, video_id):
            assert video_id == "openai-video-1"
            return b"OPENAI_VIDEO_BYTES"


    class FakeOpenAIClient:
        def __init__(self):
            self.videos = FakeOpenAIVideos()


    def test_generate_video_route_uses_host_google_profile_and_video_model(tmp_path):
        google = FakeGoogleClient()
        app = Flask(__name__)
        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "host-google-fallback",
                    "api_key": "SECRET_GOOGLE",
                    "client": google,
                }
            },
        )

        client = app.test_client()
        override = client.post(
            "/visiondirector/api/model-overrides/google",
            json={"overrides": {"VIDEO_GEN": "current-google-video-model"}},
        )
        assert override.status_code == 200

        response = client.post(
            "/visiondirector/api/ai/generate-video",
            json={
                "supplier": "google",
                "visualPrompt": "A cinematic tower",
                "narrationScript": "Welcome home.",
                "aspectRatio": "16:9",
                "seconds": "8",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["supplier"] == "google"
        assert payload["model"] == "current-google-video-model"
        assert payload["url"] == "data:video/mp4;base64,GOOGLE_VIDEO_B64"
        assert google.models.calls[-1]["model"] == "current-google-video-model"
        assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


    def test_generate_video_route_uses_host_openai_profile_and_returns_data_url(tmp_path):
        openai = FakeOpenAIClient()
        app = Flask(__name__)
        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "assistant": {
                    "provider": "openai",
                    "model": "host-openai-fallback",
                    "api_key": "SECRET_OPENAI",
                    "client": openai,
                }
            },
        )

        client = app.test_client()
        override = client.post(
            "/visiondirector/api/model-overrides/openai",
            json={"overrides": {"VIDEO_GEN": "current-openai-video-model"}},
        )
        assert override.status_code == 200

        response = client.post(
            "/visiondirector/api/ai/generate-video",
            json={
                "supplier": "openai",
                "visualPrompt": "A cinematic tower",
                "narrationScript": "Welcome home.",
                "aspectRatio": "9:16",
                "seconds": "8",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()

        expected_b64 = base64.b64encode(b"OPENAI_VIDEO_BYTES").decode("ascii")
        assert payload["supplier"] == "openai"
        assert payload["model"] == "current-openai-video-model"
        assert payload["url"] == f"data:video/mp4;base64,{expected_b64}"
        assert openai.videos.calls[-1]["model"] == "current-openai-video-model"
        assert "SECRET_OPENAI" not in response.get_data(as_text=True)


    def test_runtime_js_patches_video_generation_to_backend(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path)

        response = app.test_client().get("/visiondirector/index.js")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "__smxVisionDirectorGenerateVideo" in body
        assert "/visiondirector/api/ai/generate-video" in body
        assert 'googleProvider.generateVideo = ' in body
        assert 'openaiProvider.generateVideo = ' in body
    """,
)

print("Patch complete: host-backed generateVideo migration is ready.")
