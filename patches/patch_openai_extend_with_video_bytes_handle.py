from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_openai_video_extend_bytes_contract.py")

content = runtime_file.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# 1) Add OpenAI extension byte-handle store/helpers.
# ---------------------------------------------------------------------
if "_OPENAI_VIDEO_EXTENSION_HANDLES" not in content:
    marker = "_GOOGLE_VIDEO_EXTENSION_HANDLES"
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _GOOGLE_VIDEO_EXTENSION_HANDLES anchor.")

    line_start = content.rfind("\n", 0, idx) + 1
    line_end = content.find("\n", idx)
    insert_at = line_end + 1

    content = (
        content[:insert_at]
        + '_OPENAI_VIDEO_EXTENSION_HANDLES: dict[str, bytes] = {}\n'
        + content[insert_at:]
    )
    print("Added OpenAI video extension byte-handle store.")
else:
    print("OpenAI video extension byte-handle store already present.")


if "def _smx_store_openai_video_extension_bytes(" not in content:
    marker = "def _smx_openai_extend_video_reference("
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _smx_openai_extend_video_reference anchor.")

    helper = dedent(
        '''
        def _smx_store_openai_video_extension_bytes(
            video_bytes: bytes | bytearray | None,
            *,
            provider_video_id: str | None = None,
        ) -> dict[str, str] | None:
            data = bytes(video_bytes or b"")
            if not data:
                return None

            handle = f"openai-ext-{len(_OPENAI_VIDEO_EXTENSION_HANDLES) + 1}"
            _OPENAI_VIDEO_EXTENSION_HANDLES[handle] = data

            ref = {"openaiExtensionHandle": handle}
            if provider_video_id:
                ref["providerVideoId"] = str(provider_video_id)
            return ref


        def _smx_resolve_openai_video_extension_bytes(video_to_extend: Any) -> bytes:
            if isinstance(video_to_extend, (bytes, bytearray)):
                return bytes(video_to_extend)

            handle = None
            if isinstance(video_to_extend, dict):
                for key in (
                    "openaiExtensionHandle",
                    "extensionHandle",
                    "handle",
                    "videoRef",
                ):
                    value = video_to_extend.get(key)
                    if value:
                        handle = str(value)
                        break
            else:
                value = str(video_to_extend or "").strip()
                if value:
                    handle = value

            if handle and handle in _OPENAI_VIDEO_EXTENSION_HANDLES:
                return _OPENAI_VIDEO_EXTENSION_HANDLES[handle]

            raise VisionDirectorAIExecutionError(
                "OPENAI_VIDEO_EXTENSION_REQUIRES_VIDEO_BYTES: generate a fresh OpenAI video in this running server session, then extend it before restarting."
            )


        '''
    )

    content = content[:idx] + helper + content[idx:]
    print("Added OpenAI video extension byte helpers.")
else:
    print("OpenAI video extension byte helpers already present.")


# ---------------------------------------------------------------------
# 2) Replace _smx_openai_extend_video_reference so videos.extend(video=...)
#    receives bytes, not {"id": "..."}.
# ---------------------------------------------------------------------
start = content.find("def _smx_openai_extend_video_reference(")
if start < 0:
    raise SystemExit("Could not find _smx_openai_extend_video_reference.")

end = content.find("\ndef ", start + 1)
if end < 0:
    end = len(content)

replacement = dedent(
    '''
    def _smx_openai_extend_video_reference(video_to_extend: Any) -> bytes:
        """
        The installed OpenAI Python SDK treats videos.extend(video=...) as a file
        upload parameter. Therefore the value passed to `video` must be bytes,
        IO, PathLike, or a file tuple, not a provider video id object.
        """
        return _smx_resolve_openai_video_extension_bytes(video_to_extend)
    '''
).strip()

content = content[:start] + replacement + "\n\n" + content[end:].lstrip("\n")
print("Replaced OpenAI extension reference normalizer to return bytes.")


# ---------------------------------------------------------------------
# 3) After OpenAI create/extend content is fetched, store returned MP4 bytes
#    and return the in-memory handle as videoRef.
#
# This script handles the common backend shape:
#   video_bytes = ...
#   data_url = ...
#   return _ProviderVideoResponse(... video_ref=...)
#
# It injects a local `openai_extension_ref` before the response return and
# uses it for the provider video reference.
# ---------------------------------------------------------------------
if "_smx_store_openai_video_extension_bytes(" not in content:
    raise SystemExit("OpenAI extension byte store helper missing after insertion.")

# Find the _generate_openai_video function.
func_start = content.find("def _generate_openai_video(")
if func_start < 0:
    raise SystemExit("Could not find _generate_openai_video.")

func_end = content.find("\ndef ", func_start + 1)
if func_end < 0:
    func_end = len(content)

func = content[func_start:func_end]

# First, make sure the extend call still passes through _smx_openai_extend_video_reference.
if "video=_smx_openai_extend_video_reference(video_to_extend)" not in func:
    raise SystemExit("OpenAI extend call does not use _smx_openai_extend_video_reference.")

# Locate the first _ProviderVideoResponse return in the OpenAI function.
return_marker = "return _ProviderVideoResponse("
return_idx = func.find(return_marker)
if return_idx < 0:
    raise SystemExit("Could not find _ProviderVideoResponse return inside _generate_openai_video.")

# Insert a defensive extension-ref calculation immediately before return.
if "openai_extension_ref = _smx_store_openai_video_extension_bytes(" not in func:
    insert = dedent(
        '''
            openai_extension_ref = _smx_store_openai_video_extension_bytes(
                locals().get("video_bytes") or locals().get("content") or locals().get("content_bytes"),
                provider_video_id=locals().get("video_id"),
            )

        '''
    )
    func = func[:return_idx] + insert + func[return_idx:]
    return_idx = func.find(return_marker)
    print("Inserted OpenAI extension-ref creation before provider response.")
else:
    print("OpenAI extension-ref creation already present.")

# Replace video_ref/provider video ref assignment if there is a simple old one.
old_refs = [
    'video_ref=video_id,',
    'video_ref=str(video_id),',
    'video_ref=provider_video_id,',
    'video_ref=str(provider_video_id),',
]
if "video_ref=openai_extension_ref" not in func:
    replaced = False
    for old in old_refs:
        if old in func:
            func = func.replace(old, "video_ref=openai_extension_ref or video_id,", 1)
            replaced = True
            print(f"Replaced {old} with OpenAI extension handle.")
            break

    if not replaced:
        # Some versions use provider_video_id only and no video_ref. Add/replace provider_video_id
        # cautiously by leaving existing return intact; direct tests will catch it.
        print("Could not find a simple video_ref assignment; leaving response return shape unchanged for tests to reveal.")
else:
    print("OpenAI response already uses extension ref.")

content = content[:func_start] + func + content[func_end:]
runtime_file.write_text(content, encoding="utf-8")
print("Patched ai_runtime.py")


# ---------------------------------------------------------------------
# 4) Add direct tests around the new byte-handle behavior.
# ---------------------------------------------------------------------
test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import pytest

        from smx_visiondirector.ai_runtime import (
            VisionDirectorAIExecutionError,
            _OPENAI_VIDEO_EXTENSION_HANDLES,
            _smx_openai_extend_video_reference,
            _smx_store_openai_video_extension_bytes,
        )


        def test_openai_extension_store_returns_handle_and_resolves_to_bytes():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()

            ref = _smx_store_openai_video_extension_bytes(
                b"fake-mp4-bytes",
                provider_video_id="video_123",
            )

            assert ref is not None
            assert ref["providerVideoId"] == "video_123"
            assert ref["openaiExtensionHandle"].startswith("openai-ext-")
            assert _smx_openai_extend_video_reference(ref) == b"fake-mp4-bytes"


        def test_openai_extension_reference_accepts_handle_string():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()

            ref = _smx_store_openai_video_extension_bytes(b"mp4", provider_video_id=None)

            assert ref is not None
            assert _smx_openai_extend_video_reference(ref["openaiExtensionHandle"]) == b"mp4"


        def test_openai_extension_reference_rejects_provider_id_without_bytes():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()

            with pytest.raises(VisionDirectorAIExecutionError) as exc:
                _smx_openai_extend_video_reference({"providerVideoId": "video_123"})

            assert "OPENAI_VIDEO_EXTENSION_REQUIRES_VIDEO_BYTES" in str(exc.value)
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Added OpenAI extension byte-handle contract tests.")
