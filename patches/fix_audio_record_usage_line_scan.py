from __future__ import annotations

from pathlib import Path

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

marker = "# smx-visiondirector audio runtime method bindings"
idx = content.find(marker)
if idx < 0:
    raise SystemExit("Could not find audio runtime method bindings block.")

prefix = content[:idx]
suffix = content[idx:]

if "def _smx_record_usage_if_available(" not in suffix:
    insert_anchor = "def _smx_transcribe_audio_for_provider("
    insert_idx = suffix.find(insert_anchor)
    if insert_idx < 0:
        raise SystemExit("Could not find _smx_transcribe_audio_for_provider insertion point.")

    helper = '''def _smx_record_usage_if_available(runtime: Any, **kwargs: Any) -> None:
    record_usage = getattr(runtime, "_record_usage", None)
    if callable(record_usage):
        record_usage(**kwargs)


'''
    suffix = suffix[:insert_idx] + helper + suffix[insert_idx:]
    print("added helper")
else:
    print("helper already present")

lines = suffix.splitlines()
new_lines = []
replacements = 0

for line in lines:
    stripped = line.strip()
    if stripped == "self._record_usage(":
        indent = line[: len(line) - len(line.lstrip())]
        new_lines.append(f"{indent}_smx_record_usage_if_available(")
        new_lines.append(f"{indent}    self,")
        replacements += 1
    else:
        new_lines.append(line)

suffix = "\n".join(new_lines) + "\n"

remaining = suffix.count("self._record_usage(")
runtime_file.write_text(prefix + suffix, encoding="utf-8")

print(f"replacements={replacements}")
print(f"remaining_audio_self_record_usage_calls={remaining}")

if replacements < 1:
    raise SystemExit("No audio self._record_usage calls were replaced.")
if remaining:
    raise SystemExit("Audio binding block still contains self._record_usage calls.")
