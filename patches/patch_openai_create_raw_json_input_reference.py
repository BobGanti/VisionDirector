from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
route_test_file = Path("tests/test_ai_generate_video_route.py")
http_test_file = Path("tests/test_openai_video_create_http_contract.py")

content = runtime_file.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# 1) Ensure json import exists.
# ---------------------------------------------------------------------
if "import json\n" not in content:
    if "import urllib.request\n" in content:
        content = content.replace(
            "import urllib.request\n",
            "import urllib.request\nimport json\n",
            1,
        )
    else:
        content = content.replace(
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\nimport json\n",
            1,
        )
    print("Added json import.")
else:
    print("json import already present.")


# ---------------------------------------------------------------------
# 2) Add raw JSON OpenAI create helpers.
# ---------------------------------------------------------------------
if "def _smx_openai_input_reference_json(" not in content:
    marker = "def _generate_openai_video("
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _generate_openai_video anchor.")

    helpers = dedent(
        '''
        def _smx_openai_input_reference_json(start_image_base64: str | None) -> dict[str, str] | None:
            raw = str(start_image_base64 or "").strip()
            if not raw:
                return None

            if raw.startswith("http://") or raw.startswith("https://"):
                return {"image_url": raw}

            if raw.startswith("data:image/"):
                return {"image_url": raw}

            if "base64," in raw:
                return {"image_url": raw}

            return {"image_url": "data:image/png;base64," + raw}


        def _smx_openai_create_video_via_json_endpoint(
            client: Any,
            *,
            profile: ProviderProfile,
            model: str,
            prompt: str,
            seconds: str,
            size: str,
            start_image_base64: str | None,
        ) -> Any:
            """
            Use the official OpenAI JSON video-create endpoint when a reference
            image is present.

            The OpenAI API accepts:
              {"input_reference": {"image_url": "data:image/png;base64,..."}}
            but the installed Python SDK path has treated input_reference
            inconsistently. Raw JSON keeps VisionDirector aligned with the
            official API contract.
            """
            api_key = _smx_openai_api_key(profile, client)
            url = _smx_openai_base_url(client) + "/videos"

            body: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "seconds": str(seconds or "8"),
                "size": size,
            }

            reference = _smx_openai_input_reference_json(start_image_base64)
            if reference:
                body["input_reference"] = reference

            request = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
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
                    f"OPENAI_VIDEO_CREATE_FAILED: {detail}"
                ) from exc
            except urllib.error.URLError as exc:
                raise VisionDirectorAIExecutionError(
                    f"OPENAI_VIDEO_CREATE_REQUEST_FAILED: {exc}"
                ) from exc

            try:
                return json.loads(payload)
            except json.JSONDecodeError as exc:
                raise VisionDirectorAIExecutionError(
                    "OPENAI_VIDEO_CREATE_RETURNED_INVALID_JSON"
                ) from exc


        '''
    )

    content = content[:idx] + helpers + content[idx:]
    print("Added OpenAI raw JSON create helpers.")
else:
    print("OpenAI raw JSON create helpers already present.")


# ---------------------------------------------------------------------
# 3) Patch _generate_openai_video create branch:
#    - with start image: official raw JSON endpoint
#    - without start image: existing SDK create path
# ---------------------------------------------------------------------
func_start = content.find("def _generate_openai_video(")
if func_start < 0:
    raise SystemExit("Could not find _generate_openai_video.")

func_end = content.find("\ndef _poll_google_video_operation", func_start)
if func_end < 0:
    raise SystemExit("Could not find _poll_google_video_operation after _generate_openai_video.")

func = content[func_start:func_end]

branch_start = func.find("    elif create is not None:")
if branch_start < 0:
    raise SystemExit("Could not find OpenAI create branch.")

branch_end = func.find("    else:\n        raise VisionDirectorAIExecutionError(", branch_start)
if branch_end < 0:
    raise SystemExit("Could not find OpenAI create branch end.")

new_branch = dedent(
    '''
        elif create is not None:
            kwargs: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "seconds": str(seconds or "8"),
                "size": size,
            }

            if start_image_base64:
                job = _smx_openai_create_video_via_json_endpoint(
                    client,
                    profile=profile,
                    model=model,
                    prompt=prompt,
                    seconds=str(seconds or "8"),
                    size=size,
                    start_image_base64=start_image_base64,
                )
            else:
                job = create(**kwargs)
    '''
)

func = func[:branch_start] + new_branch + func[branch_end:]
content = content[:func_start] + func + content[func_end:]

new_func = content[func_start:content.find("\ndef _poll_google_video_operation", func_start)]
if "_smx_openai_create_video_via_json_endpoint(" not in new_func:
    raise SystemExit("Raw JSON OpenAI create endpoint is not wired into _generate_openai_video.")

runtime_file.write_text(content, encoding="utf-8")
print("Wired OpenAI image-reference video creation to raw JSON endpoint.")


# ---------------------------------------------------------------------
# 4) Keep old route test stable by making its prompt-only case explicit.
# ---------------------------------------------------------------------
route_tests = route_test_file.read_text(encoding="utf-8")

old_name = "def test_generate_video_route_skips_openai_start_image_until_sdk_reference_contract_is_supported"
new_name = "def test_generate_video_route_uses_sdk_create_for_openai_prompt_only_generation"
if old_name in route_tests:
    route_tests = route_tests.replace(old_name, new_name, 1)

route_tests = route_tests.replace(
    '            "startImageBase64": start_image,\n',
    "",
    1,
)

route_tests = route_tests.replace(
    '    start_image = "data:image/png;base64,AAAA"\n',
    "",
    1,
)

route_test_file.write_text(route_tests, encoding="utf-8")
print("Adjusted route test to cover prompt-only SDK create path.")


# ---------------------------------------------------------------------
# 5) Add direct raw JSON create contract tests.
# ---------------------------------------------------------------------
http_test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        import json
        from types import SimpleNamespace

        from smx_visiondirector import ai_runtime
        from smx_visiondirector.ai_runtime import (
            _smx_openai_create_video_via_json_endpoint,
            _smx_openai_input_reference_json,
        )


        class FakeResponse:
            def __init__(self, payload: bytes):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.payload


        def test_openai_input_reference_json_accepts_data_url():
            ref = _smx_openai_input_reference_json("data:image/png;base64,AAAA")

            assert ref == {"image_url": "data:image/png;base64,AAAA"}


        def test_openai_input_reference_json_wraps_raw_base64_as_png_data_url():
            ref = _smx_openai_input_reference_json("AAAA")

            assert ref == {"image_url": "data:image/png;base64,AAAA"}


        def test_openai_raw_json_create_posts_input_reference(monkeypatch):
            captured = {}

            def fake_urlopen(request, timeout):
                captured["url"] = request.full_url
                captured["timeout"] = timeout
                captured["headers"] = dict(request.header_items())
                captured["body"] = json.loads(request.data.decode("utf-8"))
                return FakeResponse(b'{"id":"video_123","status":"queued"}')

            monkeypatch.setattr(ai_runtime.urllib.request, "urlopen", fake_urlopen)

            client = SimpleNamespace(
                api_key="sk-test",
                base_url="https://api.openai.com/v1",
            )
            profile = SimpleNamespace(api_key="sk-profile")

            result = _smx_openai_create_video_via_json_endpoint(
                client,
                profile=profile,
                model="sora-2",
                prompt="animate this starting frame",
                seconds="8",
                size="1280x720",
                start_image_base64="data:image/png;base64,AAAA",
            )

            assert result["id"] == "video_123"
            assert captured["url"] == "https://api.openai.com/v1/videos"
            assert captured["body"] == {
                "model": "sora-2",
                "prompt": "animate this starting frame",
                "seconds": "8",
                "size": "1280x720",
                "input_reference": {"image_url": "data:image/png;base64,AAAA"},
            }
            assert captured["headers"]["Authorization"] == "Bearer sk-test"
            assert captured["headers"]["Content-type"] == "application/json"
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Added OpenAI raw JSON create contract tests.")
