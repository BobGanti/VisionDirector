from __future__ import annotations

from pathlib import Path

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

bad_start = content.find("\ndef transcribe_audio_for_provider(\n")
if bad_start < 0:
    raise SystemExit("Could not find misplaced module-level transcribe_audio_for_provider block.")

good_resume = content.find("\n    def generate_video_for_provider(", bad_start)
if good_resume < 0:
    raise SystemExit("Could not find class generate_video_for_provider resume point.")

removed = content[bad_start:good_resume]
content = content[:bad_start] + "\n" + content[good_resume:]

runtime_file.write_text(content, encoding="utf-8")

print("Removed misplaced module-level audio runtime block.")
print(f"Removed lines: {removed.count(chr(10))}")
