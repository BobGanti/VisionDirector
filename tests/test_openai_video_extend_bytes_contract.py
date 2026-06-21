from __future__ import annotations

import pytest

from smx_visiondirector.ai_runtime import (
    VisionDirectorAIExecutionError,
    _OPENAI_VIDEO_EXTENSION_HANDLES,
    _smx_openai_extend_video_reference,
    _smx_store_openai_video_extension_bytes,
)


def test_openai_extension_store_returns_handle_and_resolves_to_bytes():
    _OPENAI_VIDEO_EXTENSION_HANDLES.clear()

    ref = _smx_store_openai_video_extension_bytes(
        b"fake-mp4-bytes",
        provider_video_id="video_123",
    )

    assert ref is not None
    assert ref["providerVideoId"] == "video_123"
    assert ref["openaiExtensionHandle"].startswith("openai-ext-")
    assert _smx_openai_extend_video_reference(ref) == b"fake-mp4-bytes"


def test_openai_extension_reference_accepts_handle_string():
    _OPENAI_VIDEO_EXTENSION_HANDLES.clear()

    ref = _smx_store_openai_video_extension_bytes(b"mp4", provider_video_id=None)

    assert ref is not None
    assert _smx_openai_extend_video_reference(ref["openaiExtensionHandle"]) == b"mp4"


def test_openai_extension_reference_rejects_provider_id_without_bytes():
    _OPENAI_VIDEO_EXTENSION_HANDLES.clear()

    with pytest.raises(VisionDirectorAIExecutionError) as exc:
        _smx_openai_extend_video_reference({"providerVideoId": "video_123"})

    assert "OPENAI_VIDEO_EXTENSION_REQUIRES_VIDEO_BYTES" in str(exc.value)
