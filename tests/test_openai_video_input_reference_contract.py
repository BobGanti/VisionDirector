from __future__ import annotations

import pytest

from smx_visiondirector.ai_runtime import (
    VisionDirectorAIExecutionError,
    _smx_openai_input_reference,
)


def test_openai_video_input_reference_data_url_returns_bytes():
    result = _smx_openai_input_reference("data:image/png;base64,AAAA")

    assert result == b"\x00\x00\x00"
    assert isinstance(result, bytes)


def test_openai_video_input_reference_raw_base64_returns_bytes():
    result = _smx_openai_input_reference("AAAA")

    assert result == b"\x00\x00\x00"
    assert isinstance(result, bytes)


def test_openai_video_input_reference_does_not_accept_url_dict_shape():
    with pytest.raises(VisionDirectorAIExecutionError) as exc:
        _smx_openai_input_reference("https://example.com/frame.png")

    assert str(exc.value) == "OPENAI_VIDEO_INPUT_REFERENCE_URL_UNSUPPORTED"
