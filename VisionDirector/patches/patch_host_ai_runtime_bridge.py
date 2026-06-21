from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not init_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/__init__.py. Run from VisionDirector root.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


write_file(
    "src/smx_visiondirector/ai_runtime.py",
    '''
    from __future__ import annotations

    from dataclasses import dataclass
    from typing import Any

    from .ai_profiles import (
        AIProfileRegistry,
        ProviderProfile,
        VisionDirectorAIProfileError,
    )


    class VisionDirectorAIExecutionError(RuntimeError):
        """Raised when a host-provided AI client cannot execute the request."""


    @dataclass(frozen=True)
    class AITextResult:
        role: str
        provider: str
        model: str | None
        text: str


    class VisionDirectorAIRuntime:
        """Executes AI work using host-provided model clients only."""

        def __init__(self, profile_registry: AIProfileRegistry):
            self.profile_registry = profile_registry

        def generate_text(
            self,
            *,
            prompt: str,
            role: str = "main",
            model: str | None = None,
        ) -> AITextResult:
            clean_prompt = str(prompt or "").strip()
            if not clean_prompt:
                raise VisionDirectorAIExecutionError("prompt is required")

            profile = self.profile_registry.require_role(role)
            selected_model = model or profile.model

            if not selected_model:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host ai_profile['{role}']['model'] is missing."
                )

            if profile.provider == "google":
                text = _generate_google_text(profile, prompt=clean_prompt, model=selected_model)
            elif profile.provider == "openai":
                text = _generate_openai_text(profile, prompt=clean_prompt, model=selected_model)
            else:
                raise VisionDirectorAIExecutionError(
                    f"Unsupported VisionDirector text provider: {profile.provider}"
                )

            return AITextResult(
                role=role,
                provider=profile.provider,
                model=selected_model,
                text=text,
            )


    def build_ai_runtime(profile_registry: AIProfileRegistry) -> VisionDirectorAIRuntime:
        return VisionDirectorAIRuntime(profile_registry)


    def _generate_google_text(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
    ) -> str:
        client = profile.client
        models = getattr(client, "models", None)

        if models is None or not hasattr(models, "generate_content"):
            raise VisionDirectorAIExecutionError(
                "Google host client must expose client.models.generate_content(...)."
            )

        response = models.generate_content(
            model=model,
            contents=prompt,
        )

        return _extract_text(response)


    def _generate_openai_text(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
    ) -> str:
        client = profile.client
        responses = getattr(client, "responses", None)

        if responses is None or not hasattr(responses, "create"):
            raise VisionDirectorAIExecutionError(
                "OpenAI host client must expose client.responses.create(...)."
            )

        response = responses.create(
            model=model,
            input=prompt,
        )

        return _extract_text(response)


    def _extract_text(response: Any) -> str:
        direct = getattr(response, "text", None)
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        if isinstance(response, dict):
            for key in ("text", "output_text"):
                value = response.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        raise VisionDirectorAIExecutionError("AI response did not contain text output.")
    ''',
)


content = init_file.read_text(encoding="utf-8")

content = content.replace(
    "from .ai_profiles import AIProfileRegistry, build_ai_profile_registry\n",
    "from .ai_profiles import AIProfileRegistry, VisionDirectorAIProfileError, build_ai_profile_registry\n"
    "from .ai_runtime import VisionDirectorAIExecutionError, build_ai_runtime\n",
)

marker = '    @bp.get("/assets/<path:filename>")\n'
endpoint = '''
    @bp.post("/api/ai/generate-text")
    def ai_generate_text():
        payload = request.get_json(silent=True) or {}
        role = str(payload.get("role") or "main").strip().lower()
        prompt = str(payload.get("prompt") or "").strip()
        model = str(payload.get("model") or "").strip() or None

        try:
            result = build_ai_runtime(profile_registry).generate_text(
                role=role,
                prompt=prompt,
                model=model,
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "role": result.role,
            "provider": result.provider,
            "model": result.model,
            "text": result.text,
        }


'''

if endpoint.strip() not in content:
    if marker not in content:
        raise SystemExit("Could not find assets route marker in __init__.py.")
    content = content.replace(marker, endpoint + marker, 1)

content = content.replace(
    '    "AIProfileRegistry",\n',
    '    "AIProfileRegistry",\n    "VisionDirectorAIExecutionError",\n',
)

init_file.write_text(content, encoding="utf-8")
print("updated src/smx_visiondirector/__init__.py with host AI runtime endpoint")

write_file(
    "tests/test_ai_runtime_bridge.py",
    '''
    from __future__ import annotations

    import pytest

    from smx_visiondirector.ai_profiles import build_ai_profile_registry
    from smx_visiondirector.ai_runtime import (
        VisionDirectorAIExecutionError,
        build_ai_runtime,
    )


    class FakeGoogleModels:
        def __init__(self):
            self.calls = []

        def generate_content(self, *, model, contents):
            self.calls.append({"model": model, "contents": contents})
            return {"text": "google text result"}


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    class FakeOpenAIResponses:
        def __init__(self):
            self.calls = []

        def create(self, *, model, input):
            self.calls.append({"model": model, "input": input})
            return {"output_text": "openai text result"}


    class FakeOpenAIClient:
        def __init__(self):
            self.responses = FakeOpenAIResponses()


    def test_google_main_text_generation_uses_host_client_and_model():
        client = FakeGoogleClient()
        registry = build_ai_profile_registry(
            {
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "SECRET_GOOGLE",
                    "client": client,
                }
            }
        )

        result = build_ai_runtime(registry).generate_text(
            role="main",
            prompt="Parse this script.",
        )

        assert result.provider == "google"
        assert result.model == "gemini-2.5-flash"
        assert result.text == "google text result"
        assert client.models.calls == [
            {
                "model": "gemini-2.5-flash",
                "contents": "Parse this script.",
            }
        ]


    def test_openai_assistant_text_generation_uses_host_client_and_model():
        client = FakeOpenAIClient()
        registry = build_ai_profile_registry(
            {
                "assistant": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "SECRET_OPENAI",
                    "client": client,
                }
            }
        )

        result = build_ai_runtime(registry).generate_text(
            role="assistant",
            prompt="Improve this narration.",
        )

        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"
        assert result.text == "openai text result"
        assert client.responses.calls == [
            {
                "model": "gpt-4o-mini",
                "input": "Improve this narration.",
            }
        ]


    def test_empty_prompt_is_rejected_before_calling_model():
        client = FakeGoogleClient()
        registry = build_ai_profile_registry(
            {
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "client": client,
                }
            }
        )

        with pytest.raises(VisionDirectorAIExecutionError, match="prompt is required"):
            build_ai_runtime(registry).generate_text(role="main", prompt="  ")

        assert client.models.calls == []
    ''',
)

write_file(
    "tests/test_ai_runtime_route.py",
    '''
    from __future__ import annotations

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeGoogleModels:
        def generate_content(self, *, model, contents):
            return {"text": f"google:{model}:{contents}"}


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    def test_ai_generate_text_route_uses_host_main_profile(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "SECRET_GOOGLE",
                    "client": FakeGoogleClient(),
                }
            },
        )

        response = app.test_client().post(
            "/visiondirector/api/ai/generate-text",
            json={
                "role": "main",
                "prompt": "hello",
            },
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "role": "main",
            "provider": "google",
            "model": "gemini-2.5-flash",
            "text": "google:gemini-2.5-flash:hello",
        }

        assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


    def test_ai_generate_text_route_reports_missing_host_profile(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path, ai_profile={})

        response = app.test_client().post(
            "/visiondirector/api/ai/generate-text",
            json={
                "role": "main",
                "prompt": "hello",
            },
        )

        assert response.status_code == 503
        assert "ai_profile['main']" in response.get_json()["error"]
    ''',
)

print("Patch complete: VisionDirector has a host-client AI runtime bridge.")
