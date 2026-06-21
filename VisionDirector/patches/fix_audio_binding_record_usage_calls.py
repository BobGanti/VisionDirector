from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

marker = "# smx-visiondirector audio runtime method bindings"
idx = content.find(marker)
if idx < 0:
    raise SystemExit("Could not find audio runtime method bindings block.")

prefix = content[:idx]
suffix = content[idx:]

if "def _smx_record_usage_if_available(" not in suffix:
    insert_at = suffix.find("\ndef _smx_transcribe_audio_for_provider(")
    if insert_at < 0:
        raise SystemExit("Could not find audio transcribe binding insertion point.")

    helper = dedent(
        '''
        
        def _smx_record_usage_if_available(runtime: Any, **kwargs: Any) -> None:
            record_usage = getattr(runtime, "_record_usage", None)
            if callable(record_usage):
                record_usage(**kwargs)
        '''
    )

    suffix = suffix[:insert_at] + helper + suffix[insert_at:]
    print("added _smx_record_usage_if_available helper")
else:
    print("_smx_record_usage_if_available helper already exists")

before = suffix.count("self._record_usage(")
suffix = suffix.replace(
    "                self._record_usage(\n",
    "                _smx_record_usage_if_available(\n                    self,\n",
)
after = suffix.count("self._record_usage(")

runtime_file.write_text(prefix + suffix, encoding="utf-8")

print(f"replaced audio self._record_usage calls: {before - after}")
if after:
    raise SystemExit(f"Still found {after} self._record_usage call(s) in audio binding block.")
