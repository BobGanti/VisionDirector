from __future__ import annotations

from pathlib import Path

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_ai_generate_video_route.py")

content = runtime_file.read_text(encoding="utf-8")

old_block = '''        input_reference = _smx_openai_input_reference(start_image_base64)
        if input_reference:
            kwargs["input_reference"] = input_reference
'''

new_block = '''        # Do not pass input_reference through the OpenAI Python SDK yet.
        #
        # Current OpenAI API docs define input_reference as a JSON object with
        # image_url or file_id, but the installed Python SDK serializes the
        # videos.create(input_reference=...) parameter as a file upload. That
        # causes the server to reject it as "expected an object, but got a file".
        #
        # Until we add a raw JSON/file_id path for OpenAI image-reference video,
        # OpenAI generation falls back to prompt-only text-to-video.
        _ = start_image_base64
'''

if old_block not in content:
    if "OpenAI generation falls back to prompt-only text-to-video" in content:
        print("OpenAI input_reference is already skipped.")
    else:
        raise SystemExit("Could not find OpenAI input_reference block.")
else:
    content = content.replace(old_block, new_block, 1)
    runtime_file.write_text(content, encoding="utf-8")
    print("Patched OpenAI video generation to skip input_reference for now.")


tests = test_file.read_text(encoding="utf-8")

tests = tests.replace(
    "def test_generate_video_route_sends_openai_start_image_as_input_reference",
    "def test_generate_video_route_skips_openai_start_image_until_sdk_reference_contract_is_supported",
    1,
)

old_assertion = '''    assert openai.videos.calls[-1]["input_reference"] == b"\\x00\\x00\\x00"
    assert isinstance(openai.videos.calls[-1]["input_reference"], bytes)
'''

new_assertion = '''    assert "input_reference" not in openai.videos.calls[-1]
'''

if old_assertion in tests:
    tests = tests.replace(old_assertion, new_assertion, 1)
elif 'assert "input_reference" not in openai.videos.calls[-1]' in tests:
    print("OpenAI input_reference test already expects omission.")
else:
    raise SystemExit("Could not find OpenAI input_reference assertion block to replace.")

test_file.write_text(tests, encoding="utf-8")
print("Patched OpenAI video route test to expect prompt-only fallback.")
