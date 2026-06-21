from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_openai_video_extend_contract.py")

content = runtime_file.read_text(encoding="utf-8")

if "def _smx_openai_extend_video_reference(" not in content:
    marker = "def _generate_openai_video("
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _generate_openai_video anchor.")

    helper = dedent(
        '''
        def _smx_openai_extend_video_reference(video_to_extend: Any) -> dict[str, str]:
            """
            OpenAI videos.extend() expects a video reference object.

            The generated OpenAI clip may be represented internally as a plain
            provider video id, a dict payload, or an SDK object with an id.
            Normalize all supported forms to: {"id": "..."}.
            """
            if isinstance(video_to_extend, dict):
                for key in ("id", "video_id", "provider_video_id", "providerVideoId"):
                    value = video_to_extend.get(key)
                    if value:
                        return {"id": str(value)}

            for attr in ("id", "video_id", "provider_video_id", "providerVideoId"):
                value = getattr(video_to_extend, attr, None)
                if value:
                    return {"id": str(value)}

            value = str(video_to_extend or "").strip()
            if value:
                return {"id": value}

            raise VisionDirectorAIExecutionError(
                "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"
            )


        '''
    )

    content = content[:idx] + helper + content[idx:]
    print("Added OpenAI extension video-reference normalizer.")
else:
    print("OpenAI extension video-reference normalizer already present.")


func_start = content.find("def _generate_openai_video(")
if func_start < 0:
    raise SystemExit("Could not find _generate_openai_video.")

func_end = content.find("\ndef ", func_start + 1)
if func_end < 0:
    func_end = len(content)

func = content[func_start:func_end]

if 'getattr(videos, "remix", None)' not in func and 'getattr(videos, "extend", None)' in func:
    print("_generate_openai_video already uses videos.extend.")
else:
    block_start = func.find("    if video_to_extend:")
    if block_start < 0:
        raise SystemExit("Could not find video_to_extend branch.")

    create_anchor = '        create = getattr(videos, "create", None)'
    block_end = func.find(create_anchor, block_start)
    if block_end < 0:
        raise SystemExit("Could not find OpenAI create branch anchor after video_to_extend.")

    replacement = dedent(
        '''
            if video_to_extend:
                extend = getattr(videos, "extend", None)
                if extend is None:
                    raise VisionDirectorAIExecutionError(
                        "OPENAI_VIDEO_EXTENSION_NOT_SUPPORTED"
                    )

                job = extend(
                    prompt=prompt,
                    seconds=seconds,
                    video=_smx_openai_extend_video_reference(video_to_extend),
                )
            else:
        '''
    )

    func = func[:block_start] + replacement + func[block_end:]
    content = content[:func_start] + func + content[func_end:]
    runtime_file.write_text(content, encoding="utf-8")
    print("Patched OpenAI extension branch to use videos.extend().")

if 'getattr(videos, "remix", None)' in runtime_file.read_text(encoding="utf-8"):
    raise SystemExit("Old OpenAI videos.remix usage is still present.")

print("Verified old OpenAI videos.remix usage is gone.")


test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import inspect

        import pytest

        from smx_visiondirector.ai_runtime import (
            VisionDirectorAIExecutionError,
            _generate_openai_video,
            _smx_openai_extend_video_reference,
        )


        def test_openai_extend_video_reference_accepts_string_id():
            assert _smx_openai_extend_video_reference("video_123") == {"id": "video_123"}


        def test_openai_extend_video_reference_accepts_dict_id():
            assert _smx_openai_extend_video_reference({"id": "video_456"}) == {"id": "video_456"}


        def test_openai_extend_video_reference_rejects_empty_reference():
            with pytest.raises(VisionDirectorAIExecutionError) as exc:
                _smx_openai_extend_video_reference("")

            assert str(exc.value) == "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"


        def test_openai_extension_uses_extend_endpoint_not_remix():
            source = inspect.getsource(_generate_openai_video)

            assert 'getattr(videos, "extend", None)' in source
            assert 'getattr(videos, "remix", None)' not in source
            assert "video=_smx_openai_extend_video_reference(video_to_extend)" in source
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Added OpenAI extension contract tests.")
