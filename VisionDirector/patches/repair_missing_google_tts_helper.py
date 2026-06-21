from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

if "def _smx_resolve_google_tts_model(" in content:
    print("Google TTS helper already exists.")
else:
    marker = "# smx-visiondirector provider-backed TTS preview bindings"
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find provider-backed TTS preview bindings marker.")

    line_end = content.find("\n", idx)
    if line_end < 0:
        raise SystemExit("Could not find marker line end.")

    helper = dedent(
        '''


        GOOGLE_TTS_PREVIEW_MODEL = "gemini-3.1-flash-tts-preview"


        def _smx_is_google_tts_model(model: str | None) -> bool:
            return "tts" in str(model or "").strip().lower()


        def _smx_resolve_google_tts_model(model: str | None) -> str:
            if _smx_is_google_tts_model(model):
                return str(model).strip()
            return GOOGLE_TTS_PREVIEW_MODEL
        '''
    )

    content = content[:line_end] + helper + content[line_end:]
    runtime_file.write_text(content, encoding="utf-8")
    print("Inserted missing Google TTS helper functions.")
