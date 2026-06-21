from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
contract_test_file = Path("tests/test_openai_video_extend_contract.py")

content = runtime_file.read_text(encoding="utf-8")

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
        extend = getattr(videos, "extend", None)

        if video_to_extend:
            if extend is None:
                raise VisionDirectorAIExecutionError(
                    "OPENAI_VIDEO_EXTENSION_NOT_SUPPORTED"
                )

            job = extend(
                prompt=prompt,
                seconds=str(seconds or "8"),
                video=_smx_openai_extend_video_reference(video_to_extend),
            )
        elif create is not None:
            kwargs: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "seconds": str(seconds or "8"),
                "size": size,
            }

            # Do not pass input_reference through the OpenAI Python SDK yet.
            # The installed SDK currently treats it as a file upload while the
            # server-side API expects a JSON object, so prompt-only video
            # generation is the stable path for now.
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
print("Replaced _generate_openai_video with clean byte-handle implementation.")


contract_test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import inspect

        import pytest

        from smx_visiondirector.ai_runtime import (
            VisionDirectorAIExecutionError,
            _OPENAI_VIDEO_EXTENSION_HANDLES,
            _generate_openai_video,
            _smx_openai_extend_video_reference,
            _smx_store_openai_video_extension_bytes,
        )


        def test_openai_extend_video_reference_accepts_stored_handle_string():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()
            ref = _smx_store_openai_video_extension_bytes(b"mp4-bytes")

            assert ref is not None
            assert _smx_openai_extend_video_reference(ref["openaiExtensionHandle"]) == b"mp4-bytes"


        def test_openai_extend_video_reference_accepts_dict_handle():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()
            ref = _smx_store_openai_video_extension_bytes(
                b"mp4-bytes",
                provider_video_id="video_456",
            )

            assert ref is not None
            assert _smx_openai_extend_video_reference(ref) == b"mp4-bytes"


        def test_openai_extend_video_reference_rejects_provider_id_without_bytes():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()

            with pytest.raises(VisionDirectorAIExecutionError) as exc:
                _smx_openai_extend_video_reference({"providerVideoId": "video_789"})

            assert "OPENAI_VIDEO_EXTENSION_REQUIRES_VIDEO_BYTES" in str(exc.value)


        def test_openai_extension_uses_extend_endpoint_not_remix():
            source = inspect.getsource(_generate_openai_video)

            assert 'getattr(videos, "extend", None)' in source
            assert 'getattr(videos, "remix", None)' not in source
            assert "video=_smx_openai_extend_video_reference(video_to_extend)" in source
            assert "job = extend(" in source
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Rewrote OpenAI extension contract tests for byte-handle behavior.")
