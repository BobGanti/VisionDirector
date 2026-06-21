from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_openai_video_input_reference_contract.py")

content = runtime_file.read_text(encoding="utf-8")

replacement = dedent(
    '''
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
    '''
).strip()

count = 0
while True:
    start = content.find("def _smx_openai_input_reference(")
    if start < 0:
        break

    end = content.find("\ndef ", start + 1)
    if end < 0:
        end = len(content)

    content = content[:start] + replacement + "\n\n" + content[end:].lstrip("\n")
    count += 1

if count < 1:
    raise SystemExit("No _smx_openai_input_reference function was found to replace.")

if 'return {"image_url"' in content:
    raise SystemExit('Old dict-returning OpenAI input_reference logic is still present.')

runtime_file.write_text(content, encoding="utf-8")
print(f"Replaced {count} _smx_openai_input_reference function definition(s).")
print("Verified old dict-returning logic is gone.")


test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import pytest

        from smx_visiondirector.ai_runtime import (
            VisionDirectorAIExecutionError,
            _smx_openai_input_reference,
        )


        def test_openai_video_input_reference_data_url_returns_bytes():
            result = _smx_openai_input_reference("data:image/png;base64,AAAA")

            assert result == b"\\x00\\x00\\x00"
            assert isinstance(result, bytes)


        def test_openai_video_input_reference_raw_base64_returns_bytes():
            result = _smx_openai_input_reference("AAAA")

            assert result == b"\\x00\\x00\\x00"
            assert isinstance(result, bytes)


        def test_openai_video_input_reference_does_not_accept_url_dict_shape():
            with pytest.raises(VisionDirectorAIExecutionError) as exc:
                _smx_openai_input_reference("https://example.com/frame.png")

            assert str(exc.value) == "OPENAI_VIDEO_INPUT_REFERENCE_URL_UNSUPPORTED"
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Added direct OpenAI input_reference contract tests.")
