from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# 1) Ensure json import exists.
# ---------------------------------------------------------------------
if "import json\n" not in content:
    if "import urllib.request\n" in content:
        content = content.replace("import urllib.request\n", "import urllib.request\nimport json\n", 1)
    else:
        content = content.replace("from __future__ import annotations\n\n", "from __future__ import annotations\n\nimport json\n", 1)
    print("Added missing json import.")
else:
    print("json import already present.")


# ---------------------------------------------------------------------
# 2) Replace _smx_openai_extension_video_id cleanly.
# ---------------------------------------------------------------------
start = content.find("def _smx_openai_extension_video_id(")
if start < 0:
    raise SystemExit("Could not find _smx_openai_extension_video_id.")

end = content.find("\ndef ", start + 1)
if end < 0:
    raise SystemExit("Could not find end of _smx_openai_extension_video_id.")

replacement = dedent(
    '''
    def _smx_openai_extension_video_id(video_to_extend: Any) -> str:
        """
        Resolve the OpenAI provider video id required by the official
        /videos/extensions JSON endpoint.

        Local handles such as openai-ext-1 are only valid if they were mapped
        to the original provider video id when the video was generated.
        """
        if isinstance(video_to_extend, dict):
            handle = (
                video_to_extend.get("openaiExtensionHandle")
                or video_to_extend.get("extensionHandle")
                or video_to_extend.get("handle")
                or video_to_extend.get("videoRef")
            )
            if handle:
                handle_key = str(handle)
                if handle_key in _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS:
                    return _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[handle_key]

            for key in ("providerVideoId", "provider_video_id", "video_id", "id"):
                value = video_to_extend.get(key)
                if value:
                    return str(value)

            raise VisionDirectorAIExecutionError(
                "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"
            )

        for attr in ("providerVideoId", "provider_video_id", "video_id", "id"):
            value = getattr(video_to_extend, attr, None)
            if value:
                return str(value)

        value = str(video_to_extend or "").strip()
        if value in _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS:
            return _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[value]

        if value and not value.startswith("openai-ext-"):
            return value

        raise VisionDirectorAIExecutionError(
            "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"
        )
    '''
).strip()

content = content[:start] + replacement + "\n\n" + content[end:].lstrip("\n")
print("Replaced _smx_openai_extension_video_id with strict provider-id resolver.")


# ---------------------------------------------------------------------
# 3) Force _generate_openai_video extension branch to use official raw JSON endpoint.
# ---------------------------------------------------------------------
func_start = content.find("def _generate_openai_video(")
if func_start < 0:
    raise SystemExit("Could not find _generate_openai_video.")

func_end = content.find("\ndef _poll_google_video_operation", func_start)
if func_end < 0:
    raise SystemExit("Could not find _poll_google_video_operation after _generate_openai_video.")

func = content[func_start:func_end]

# Remove stale SDK extend lookup if present.
func = func.replace('    extend = getattr(videos, "extend", None)\n', "")

branch_start = func.find("    if video_to_extend:")
if branch_start < 0:
    raise SystemExit("Could not find if video_to_extend branch in _generate_openai_video.")

branch_end = func.find("    elif create is not None:", branch_start)
if branch_end < 0:
    raise SystemExit("Could not find elif create branch in _generate_openai_video.")

new_branch = dedent(
    '''
        if video_to_extend:
            job = _smx_openai_extend_video_via_json_endpoint(
                client,
                profile=profile,
                prompt=prompt,
                seconds=str(seconds or "8"),
                video_to_extend=video_to_extend,
            )
    '''
)

func = func[:branch_start] + new_branch + func[branch_end:]
content = content[:func_start] + func + content[func_end:]

# Safety checks.
new_func = content[func_start:content.find("\ndef _poll_google_video_operation", func_start)]
if 'getattr(videos, "extend", None)' in new_func:
    raise SystemExit("SDK videos.extend lookup still present inside _generate_openai_video.")
if "job = extend(" in new_func:
    raise SystemExit("SDK job = extend(...) still present inside _generate_openai_video.")
if "_smx_openai_extend_video_via_json_endpoint(" not in new_func:
    raise SystemExit("Raw JSON OpenAI extension endpoint is not wired into _generate_openai_video.")

runtime_file.write_text(content, encoding="utf-8")
print("Wired _generate_openai_video extension branch to raw JSON endpoint.")
