from __future__ import annotations

from pathlib import Path
from textwrap import dedent
import re

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_ai_generate_video_route.py")

content = runtime_file.read_text(encoding="utf-8")

pattern = (
    r"def _smx_openai_input_reference\(start_image_base64: str \| None\) "
    r"-> dict\[str, str\] \| None:\n"
    r"[\s\S]*?\n\n"
    r"def _smx_is_openai_video_model"
)

replacement = dedent(
    '''
    def _smx_openai_input_reference(start_image_base64: str | None) -> bytes | None:
        """
        OpenAI Python SDK video generation expects `input_reference` to be
        uploadable file content, not a JSON dict. For browser-provided data URLs
        or raw base64 strings, decode to bytes before passing to videos.create().
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


    def _smx_is_openai_video_model
    '''
).lstrip()

new_content, count = re.subn(pattern, replacement, content, count=1)

if count != 1:
    if "OpenAI Python SDK video generation expects `input_reference`" in content:
        print("OpenAI input_reference helper already repaired.")
    else:
        raise SystemExit("Could not replace _smx_openai_input_reference helper.")
else:
    content = new_content
    runtime_file.write_text(content, encoding="utf-8")
    print("Repaired OpenAI input_reference helper to return bytes.")


tests = test_file.read_text(encoding="utf-8")

old_assert = 'assert openai.videos.calls[-1]["input_reference"] == {"image_url": start_image}'
new_assert = (
    'assert openai.videos.calls[-1]["input_reference"] == b"\\x00\\x00\\x00"\\n'
    '    assert isinstance(openai.videos.calls[-1]["input_reference"], bytes)'
)

if old_assert in tests:
    tests = tests.replace(old_assert, new_assert, 1)
    test_file.write_text(tests, encoding="utf-8")
    print("Updated OpenAI input_reference test expectation to bytes.")
elif 'assert isinstance(openai.videos.calls[-1]["input_reference"], bytes)' in tests:
    print("OpenAI input_reference test already expects bytes.")
else:
    raise SystemExit("Could not find OpenAI input_reference assertion to update.")
