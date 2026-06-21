from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
contract_test_file = Path("tests/test_openai_video_extend_contract.py")
http_test_file = Path("tests/test_openai_video_extend_http_contract.py")

content = runtime_file.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# Imports for official JSON endpoint call.
# ---------------------------------------------------------------------
if "import urllib.error" not in content:
    content = content.replace(
        "from __future__ import annotations\n\n",
        "from __future__ import annotations\n\nimport urllib.error\nimport urllib.request\n",
        1,
    )
    print("Added urllib imports.")
else:
    print("urllib imports already present.")


# ---------------------------------------------------------------------
# Optional provider-id map for OpenAI extension handles.
# ---------------------------------------------------------------------
if "_OPENAI_VIDEO_EXTENSION_PROVIDER_IDS" not in content:
    content = content.replace(
        "_OPENAI_VIDEO_EXTENSION_HANDLES: dict[str, bytes] = {}\n",
        "_OPENAI_VIDEO_EXTENSION_HANDLES: dict[str, bytes] = {}\n"
        "_OPENAI_VIDEO_EXTENSION_PROVIDER_IDS: dict[str, str] = {}\n",
        1,
    )
    print("Added OpenAI extension provider-id map.")
else:
    print("OpenAI extension provider-id map already present.")


if "_OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[handle]" not in content:
    old = '''    handle = f"openai-ext-{len(_OPENAI_VIDEO_EXTENSION_HANDLES) + 1}"
    _OPENAI_VIDEO_EXTENSION_HANDLES[handle] = data

    ref = {"openaiExtensionHandle": handle}
    if provider_video_id:
        ref["providerVideoId"] = str(provider_video_id)
    return ref
'''
    new = '''    handle = f"openai-ext-{len(_OPENAI_VIDEO_EXTENSION_HANDLES) + 1}"
    _OPENAI_VIDEO_EXTENSION_HANDLES[handle] = data

    ref = {"openaiExtensionHandle": handle}
    if provider_video_id:
        _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[handle] = str(provider_video_id)
        ref["providerVideoId"] = str(provider_video_id)
    return ref
'''
    if old not in content:
        raise SystemExit("Could not patch _smx_store_openai_video_extension_bytes provider-id map.")
    content = content.replace(old, new, 1)
    print("Patched OpenAI extension store to preserve provider video id.")
else:
    print("OpenAI extension store already preserves provider video id.")


# ---------------------------------------------------------------------
# Add official JSON endpoint helpers.
# ---------------------------------------------------------------------
if "def _smx_openai_extension_video_id(" not in content:
    marker = "def _generate_openai_video("
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _generate_openai_video anchor.")

    helpers = dedent(
        '''
        def _smx_openai_extension_video_id(video_to_extend: Any) -> str:
            if isinstance(video_to_extend, dict):
                handle = (
                    video_to_extend.get("openaiExtensionHandle")
                    or video_to_extend.get("extensionHandle")
                    or video_to_extend.get("handle")
                    or video_to_extend.get("videoRef")
                )
                if handle and str(handle) in _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS:
                    return _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS[str(handle)]

                for key in ("providerVideoId", "provider_video_id", "video_id", "id"):
                    value = video_to_extend.get(key)
                    if value:
                        return str(value)

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


        def _smx_openai_api_key(profile: ProviderProfile, client: Any) -> str:
            value = getattr(client, "api_key", None) or getattr(profile, "api_key", None)
            token = str(value or "").strip()
            if not token:
                raise VisionDirectorAIExecutionError(
                    "OPENAI_API_KEY_MISSING_FOR_VIDEO_EXTENSION"
                )
            return token


        def _smx_openai_base_url(client: Any) -> str:
            value = str(getattr(client, "base_url", "") or OPENAI_DEFAULT_BASE_URL).strip()
            if not value or "://" not in value:
                value = OPENAI_DEFAULT_BASE_URL
            return value.rstrip("/")


        def _smx_openai_extend_video_via_json_endpoint(
            client: Any,
            *,
            profile: ProviderProfile,
            prompt: str,
            seconds: str,
            video_to_extend: Any,
        ) -> Any:
            """
            Use the official OpenAI HTTP JSON extension endpoint.

            The installed Python SDK currently serializes videos.extend(video=...)
            inconsistently for our use case, while the official HTTP API expects:
              POST /videos/extensions
              {"prompt": "...", "seconds": "4", "video": {"id": "video_123"}}
            """
            video_id = _smx_openai_extension_video_id(video_to_extend)
            api_key = _smx_openai_api_key(profile, client)
            url = _smx_openai_base_url(client) + "/videos/extensions"

            body = json.dumps(
                {
                    "prompt": prompt,
                    "seconds": str(seconds or "8"),
                    "video": {"id": video_id},
                }
            ).encode("utf-8")

            request = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise VisionDirectorAIExecutionError(
                    f"OPENAI_VIDEO_EXTENSION_FAILED: {detail}"
                ) from exc
            except urllib.error.URLError as exc:
                raise VisionDirectorAIExecutionError(
                    f"OPENAI_VIDEO_EXTENSION_REQUEST_FAILED: {exc}"
                ) from exc

            try:
                return json.loads(payload)
            except json.JSONDecodeError as exc:
                raise VisionDirectorAIExecutionError(
                    "OPENAI_VIDEO_EXTENSION_RETURNED_INVALID_JSON"
                ) from exc


        '''
    )

    content = content[:idx] + helpers + content[idx:]
    print("Added OpenAI raw JSON extension helpers.")
else:
    print("OpenAI raw JSON extension helpers already present.")


# ---------------------------------------------------------------------
# Replace videos.extend(...) branch with raw JSON endpoint call.
# ---------------------------------------------------------------------
old_branch = '''        if video_to_extend:
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

new_branch = '''        if video_to_extend:
            job = _smx_openai_extend_video_via_json_endpoint(
                client,
                profile=profile,
                prompt=prompt,
                seconds=str(seconds or "8"),
                video_to_extend=video_to_extend,
            )
        elif create is not None:
'''

if old_branch not in content:
    if "_smx_openai_extend_video_via_json_endpoint(" in content:
        print("OpenAI extension branch already uses raw JSON endpoint.")
    else:
        raise SystemExit("Could not find OpenAI SDK extend branch.")
else:
    content = content.replace(old_branch, new_branch, 1)
    print("Replaced OpenAI SDK extend branch with raw JSON endpoint branch.")


# Remove now-unused local extend lookup if present.
content = content.replace('        extend = getattr(videos, "extend", None)\n', "")

runtime_file.write_text(content, encoding="utf-8")
print("Patched ai_runtime.py")


# ---------------------------------------------------------------------
# Rewrite extension contract test so it matches the real implementation.
# ---------------------------------------------------------------------
contract_test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import inspect

        import pytest

        from smx_visiondirector.ai_runtime import (
            VisionDirectorAIExecutionError,
            _OPENAI_VIDEO_EXTENSION_HANDLES,
            _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS,
            _generate_openai_video,
            _smx_openai_extension_video_id,
            _smx_store_openai_video_extension_bytes,
        )


        def test_openai_extension_video_id_accepts_provider_video_id_dict():
            assert _smx_openai_extension_video_id({"providerVideoId": "video_123"}) == "video_123"


        def test_openai_extension_video_id_accepts_stored_handle_dict():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()
            _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS.clear()

            ref = _smx_store_openai_video_extension_bytes(
                b"mp4-bytes",
                provider_video_id="video_456",
            )

            assert ref is not None
            assert _smx_openai_extension_video_id(ref) == "video_456"


        def test_openai_extension_video_id_rejects_handle_without_provider_id():
            _OPENAI_VIDEO_EXTENSION_HANDLES.clear()
            _OPENAI_VIDEO_EXTENSION_PROVIDER_IDS.clear()

            ref = _smx_store_openai_video_extension_bytes(b"mp4-bytes")

            assert ref is not None
            with pytest.raises(VisionDirectorAIExecutionError) as exc:
                _smx_openai_extension_video_id(ref)

            assert str(exc.value) == "OPENAI_VIDEO_EXTENSION_REQUIRES_PROVIDER_VIDEO_ID"


        def test_openai_extension_uses_raw_json_endpoint_not_sdk_extend_or_remix():
            source = inspect.getsource(_generate_openai_video)

            assert "_smx_openai_extend_video_via_json_endpoint" in source
            assert 'getattr(videos, "extend", None)' not in source
            assert 'getattr(videos, "remix", None)' not in source
            assert "job = extend(" not in source
            assert "job = remix(" not in source
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Rewrote OpenAI extension contract tests.")


# ---------------------------------------------------------------------
# Add raw HTTP helper test with monkeypatched urlopen.
# ---------------------------------------------------------------------
http_test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import json
        from types import SimpleNamespace

        from smx_visiondirector import ai_runtime
        from smx_visiondirector.ai_runtime import _smx_openai_extend_video_via_json_endpoint


        class FakeResponse:
            def __init__(self, payload: bytes):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.payload


        def test_openai_raw_json_extension_posts_video_id_object(monkeypatch):
            captured = {}

            def fake_urlopen(request, timeout):
                captured["url"] = request.full_url
                captured["timeout"] = timeout
                captured["headers"] = dict(request.header_items())
                captured["body"] = json.loads(request.data.decode("utf-8"))
                return FakeResponse(b'{"id":"video_ext_123","status":"queued"}')

            monkeypatch.setattr(ai_runtime.urllib.request, "urlopen", fake_urlopen)

            client = SimpleNamespace(
                api_key="sk-test",
                base_url="https://api.openai.com/v1",
            )
            profile = SimpleNamespace(api_key="sk-profile")

            result = _smx_openai_extend_video_via_json_endpoint(
                client,
                profile=profile,
                prompt="continue the clip",
                seconds="8",
                video_to_extend={"providerVideoId": "video_123"},
            )

            assert result["id"] == "video_ext_123"
            assert captured["url"] == "https://api.openai.com/v1/videos/extensions"
            assert captured["body"] == {
                "prompt": "continue the clip",
                "seconds": "8",
                "video": {"id": "video_123"},
            }
            assert captured["headers"]["Authorization"] == "Bearer sk-test"
            assert captured["headers"]["Content-type"] == "application/json"
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Added OpenAI raw JSON extension HTTP test.")
