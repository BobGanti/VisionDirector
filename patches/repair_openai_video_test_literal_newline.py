from __future__ import annotations

from pathlib import Path

test_file = Path("tests/test_ai_generate_video_route.py")
text = test_file.read_text(encoding="utf-8")

bad = 'b"\\x00\\x00\\x00"\\n    assert isinstance'
good = 'b"\\x00\\x00\\x00"\n    assert isinstance'

if bad not in text:
    raise SystemExit("Could not find the literal broken \\n assertion.")
    
text = text.replace(bad, good, 1)
test_file.write_text(text, encoding="utf-8")
print("Repaired literal newline in OpenAI input_reference assertion.")
