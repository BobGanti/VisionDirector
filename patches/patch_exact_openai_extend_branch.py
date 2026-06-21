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

            Normalize all supported internal forms to: {"id": "..."}.
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


old = '''    size = _aspect_ratio_to_openai_video_size(aspect_ratio)
    create = getattr(videos, "create", None)
    remix = getattr(videos, "remix", None)

    if video_to_extend and remix is not None:
        job = remix(
            video=video_to_extend,
            model=model,
            prompt=prompt,
            seconds=str(seconds or "8"),
            size=size,
        )
    elif create is not None:
'''

new = '''    size = _aspect_ratio_to_openai_video_size(aspect_ratio)
    create = getattr(videos, "create", None)
    extend = getattr(videos, "extend", None)

    if video_to_extend:
        if extend is None:
            raise VisionDirectorAIExecutionError(
                "OPENAI_VIDEO_EXTENSION_NOT_SUPPORTED"
            )

        job = extend(
            prompt=prompt,
            seconds=str(seconds or "8"),
            video=_smx_openai_extend_video_reference(video_to_extend),
        )
    elif create is not None:
'''

if old not in content:
    if 'extend = getattr(videos, "extend", None)' in content and 'video=_smx_openai_extend_video_reference(video_to_extend)' in content:
        print("OpenAI extension branch already uses videos.extend().")
    else:
        raise SystemExit("Could not find exact old OpenAI remix branch.")
else:
    content = content.replace(old, new, 1)
    print("Replaced OpenAI remix branch with videos.extend branch.")

if 'getattr(videos, "remix", None)' in content:
    raise SystemExit("Old OpenAI videos.remix lookup is still present.")

runtime_file.write_text(content, encoding="utf-8")
print("Verified old OpenAI videos.remix lookup is gone.")


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


        def test_openai_extend_video_reference_accepts_provider_video_id_dict():
            assert _smx_openai_extend_video_reference(
                {"providerVideoId": "video_789"}
            ) == {"id": "video_789"}


        def test_openai_extend_video_reference_rejects_empty_reference():
            with pytest.raises(VisionDirectorAIExecutionError) as exc:
                _smx_openai_extend_video_reference("")

            assert str(exc.value) == "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"


        def test_openai_extension_uses_extend_endpoint_not_remix():
            source = inspect.getsource(_generate_openai_video)

            assert 'getattr(videos, "extend", None)' in source
            assert 'getattr(videos, "remix", None)' not in source
            assert "video=_smx_openai_extend_video_reference(video_to_extend)" in source
            assert "job = extend(" in source
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Added OpenAI extension contract tests.")
