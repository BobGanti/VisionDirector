from __future__ import annotations

from pathlib import Path

test_file = Path("tests/test_ai_generate_video_route.py")
text = test_file.read_text(encoding="utf-8")

old = 'assert openai.videos.calls[-1]["input_reference"] == {"image_url": start_image}'
new = (
    'assert openai.videos.calls[-1]["input_reference"] == b"\\x00\\x00\\x00"\\n'
    '    assert isinstance(openai.videos.calls[-1]["input_reference"], bytes)'
)

if old not in text:
    if 'assert isinstance(openai.videos.calls[-1]["input_reference"], bytes)' in text:
        print("Test expectation already uses bytes.")
    else:
        raise SystemExit("Could not find old dict-shaped input_reference assertion.")
else:
    text = text.replace(old, new, 1)
    test_file.write_text(text, encoding="utf-8")
    print("Updated OpenAI input_reference test expectation to bytes.")
