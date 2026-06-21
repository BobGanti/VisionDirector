from __future__ import annotations

import inspect

import pytest

from smx_visiondirector.ai_runtime import (
    VisionDirectorAIExecutionError,
    _OPENAI_VIDEO_EXTENSION_HANDLES,
    _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS,
    _generate_openai_video,
    _smx_openai_extension_video_id,
    _smx_store_openai_video_extension_bytes,
)


def test_openai_extension_video_id_accepts_provider_video_id_dict():
    assert _smx_openai_extension_video_id({"providerVideoId": "video_123"}) == "video_123"


def test_openai_extension_video_id_accepts_stored_handle_dict():
    _OPENAI_VIDEO_EXTENSION_HANDLES.clear()
    _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS.clear()

    ref = _smx_store_openai_video_extension_bytes(
        b"mp4-bytes",
        provider_video_id="video_456",
    )

    assert ref is not None
    assert _smx_openai_extension_video_id(ref) == "video_456"


def test_openai_extension_video_id_rejects_handle_without_provider_id():
    _OPENAI_VIDEO_EXTENSION_HANDLES.clear()
    _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS.clear()

    ref = _smx_store_openai_video_extension_bytes(b"mp4-bytes")

    assert ref is not None
    with pytest.raises(VisionDirectorAIExecutionError) as exc:
        _smx_openai_extension_video_id(ref)

    assert str(exc.value) == "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"


def test_openai_extension_uses_raw_json_endpoint_not_sdk_extend_or_remix():
    source = inspect.getsource(_generate_openai_video)

    assert "_smx_openai_extend_video_via_json_endpoint" in source
    assert 'getattr(videos, "extend", None)' not in source
    assert 'getattr(videos, "remix", None)' not in source
    assert "job = extend(" not in source
    assert "job = remix(" not in source
