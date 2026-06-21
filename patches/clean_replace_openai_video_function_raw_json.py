from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

# Ensure json import exists because the raw JSON extension helper uses it.
if "import json\n" not in content:
    if "import urllib.request\n" in content:
        content = content.replace(
            "import urllib.request\n",
            "import urllib.request\nimport json\n",
            1,
        )
    else:
        content = content.replace(
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\nimport json\n",
            1,
        )
    print("Added json import.")
else:
    print("json import already present.")

start = content.find("def _generate_openai_video(")
if start < 0:
    raise SystemExit("Could not find _generate_openai_video.")

end = content.find("\ndef _poll_google_video_operation", start)
if end < 0:
    raise SystemExit("Could not find _poll_google_video_operation after _generate_openai_video.")

replacement = dedent(
    '''
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
        elif create is not None:
            kwargs: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "seconds": str(seconds or "8"),
                "size": size,
            }

            # Do not pass input_reference through the OpenAI Python SDK yet.
            # The installed SDK currently treats input_reference as a file
            # upload while the OpenAI server expects a JSON object. Prompt-only
            # OpenAI video generation remains the stable backend path for now.
            _ = start_image_base64

            job = create(**kwargs)
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
    '''
).lstrip()

content = content[:start] + replacement.rstrip() + "\n\n" + content[end:].lstrip("\n")
runtime_file.write_text(content, encoding="utf-8")
print("Cleanly replaced _generate_openai_video with raw JSON extension implementation.")
