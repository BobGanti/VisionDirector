from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

bad = dedent(
    '''
        
    openai_extension_ref = _smx_store_openai_video_extension_bytes(
        locals().get("video_bytes") or locals().get("content") or locals().get("content_bytes"),
        provider_video_id=locals().get("video_id"),
    )

    return _ProviderVideoResponse(
            video_url=video_url,
            video_ref=str(video_id or ""),
            tokens=extract_token_breakdown(done),
        )
    '''
)

good = dedent(
    '''
        openai_video_bytes = _decode_data_url_bytes(video_url)
        openai_extension_ref = _smx_store_openai_video_extension_bytes(
            openai_video_bytes,
            provider_video_id=str(video_id or "") or None,
        )

        return _ProviderVideoResponse(
            video_url=video_url,
            video_ref=openai_extension_ref or str(video_id or ""),
            tokens=extract_token_breakdown(done),
        )
    '''
)

if bad not in content:
    # Fallback: replace by exact line-range shape from the broken section.
    start = content.find("\nopenai_extension_ref = _smx_store_openai_video_extension_bytes(")
    end = content.find("\n\ndef _poll_google_video_operation", start)
    if start < 0 or end < 0:
        raise SystemExit("Could not find broken module-level OpenAI response block.")

    content = content[:start] + "\n" + good.rstrip() + content[end:]
    print("Repaired broken module-level OpenAI response block by range.")
else:
    content = content.replace(bad, good, 1)
    print("Repaired broken module-level OpenAI response block by exact match.")

runtime_file.write_text(content, encoding="utf-8")
print("Patched OpenAI video response return inside _generate_openai_video.")
