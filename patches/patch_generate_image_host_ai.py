from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"

if not init_file.exists() or not runtime_file.exists():
    raise SystemExit("Run from VisionDirector root. Missing smx_visiondirector files.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


write_file(
    "src/smx_visiondirector/ai_runtime.py",
    """
    from __future__ import annotations

    from dataclasses import dataclass
    from typing import Any

    from .ai_profiles import (
        AIProfileRegistry,
        ProviderProfile,
        VisionDirectorAIProfileError,
    )


    class VisionDirectorAIExecutionError(RuntimeError):
        \"\"\"Raised when a host-provided AI client cannot execute the request.\"\"\"


    @dataclass(frozen=True)
    class AITextResult:
        role: str
        provider: str
        model: str | None
        text: str


    @dataclass(frozen=True)
    class AIImageResult:
        role: str
        provider: str
        model: str | None
        image_data_url: str | None


    class VisionDirectorAIRuntime:
        \"\"\"Executes AI work using host-provided model clients only.\"\"\"

        def __init__(self, profile_registry: AIProfileRegistry):
            self.profile_registry = profile_registry

        def generate_text(
            self,
            *,
            prompt: str,
            role: str = "main",
            model: str | None = None,
        ) -> AITextResult:
            profile = self.profile_registry.require_role(role)
            return self._generate_text_with_profile(
                profile=profile,
                prompt=prompt,
                role=role,
                model=model,
            )

        def generate_text_for_provider(
            self,
            *,
            prompt: str,
            provider: str,
            model: str | None = None,
        ) -> AITextResult:
            clean_provider = str(provider or "").strip().lower()
            profile = self.profile_registry.require_provider(clean_provider)
            return self._generate_text_with_profile(
                profile=profile,
                prompt=prompt,
                role=profile.role or clean_provider,
                model=model,
            )

        def generate_image_for_provider(
            self,
            *,
            prompt: str,
            provider: str,
            aspect_ratio: str = "9:16",
            model: str | None = None,
        ) -> AIImageResult:
            clean_provider = str(provider or "").strip().lower()
            profile = self.profile_registry.require_provider(clean_provider)

            clean_prompt = str(prompt or "").strip()
            if not clean_prompt:
                return AIImageResult(
                    role=profile.role or clean_provider,
                    provider=profile.provider,
                    model=model or profile.model,
                    image_data_url=None,
                )

            selected_model = model or profile.model
            if not selected_model:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host AI profile for provider '{profile.provider}' has no model."
                )

            if profile.provider == "google":
                image_data_url = _generate_google_image(
                    profile,
                    prompt=clean_prompt,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                )
            elif profile.provider == "openai":
                image_data_url = _generate_openai_image(
                    profile,
                    prompt=clean_prompt,
                    model=selected_model,
                    aspect_ratio=aspect_ratio,
                )
            else:
                raise VisionDirectorAIExecutionError(
                    f"Unsupported VisionDirector image provider: {profile.provider}"
                )

            return AIImageResult(
                role=profile.role or clean_provider,
                provider=profile.provider,
                model=selected_model,
                image_data_url=image_data_url,
            )

        def _generate_text_with_profile(
            self,
            *,
            profile: ProviderProfile,
            prompt: str,
            role: str,
            model: str | None = None,
        ) -> AITextResult:
            clean_prompt = str(prompt or "").strip()
            if not clean_prompt:
                raise VisionDirectorAIExecutionError("prompt is required")

            selected_model = model or profile.model
            if not selected_model:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host AI profile for provider '{profile.provider}' has no model."
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


    def _generate_google_image(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
        aspect_ratio: str,
    ) -> str | None:
        client = profile.client
        models = getattr(client, "models", None)

        if models is None or not hasattr(models, "generate_content"):
            raise VisionDirectorAIExecutionError(
                "Google host client must expose client.models.generate_content(...)."
            )

        response = models.generate_content(
            model=model,
            contents={
                "parts": [
                    {
                        "text": (
                            "High-fidelity cinematic production keyframe: "
                            f"{prompt}. Photo-realistic lighting."
                        )
                    }
                ]
            },
            config={"imageConfig": {"aspectRatio": aspect_ratio}},
        )

        b64 = _extract_inline_image_b64(response)
        return f"data:image/png;base64,{b64}" if b64 else None


    def _generate_openai_image(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
        aspect_ratio: str,
    ) -> str | None:
        client = profile.client
        images = getattr(client, "images", None)

        if images is None or not hasattr(images, "generate"):
            raise VisionDirectorAIExecutionError(
                "OpenAI host client must expose client.images.generate(...)."
            )

        response = images.generate(
            model=model,
            prompt=prompt,
            size=_aspect_ratio_to_openai_size(aspect_ratio),
            n=1,
            output_format="png",
            quality="auto",
            background="auto",
        )

        b64 = _extract_openai_image_b64(response)
        return f"data:image/png;base64,{b64}" if b64 else None


    def _aspect_ratio_to_openai_size(aspect_ratio: str) -> str:
        if aspect_ratio == "16:9":
            return "1536x1024"
        if aspect_ratio == "9:16":
            return "1024x1536"
        return "1024x1024"


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


    def _extract_inline_image_b64(response: Any) -> str | None:
        candidates = _get_value(response, "candidates") or []
        for candidate in candidates:
            content = _get_value(candidate, "content") or {}
            parts = _get_value(content, "parts") or []
            for part in parts:
                inline_data = _get_value(part, "inlineData") or _get_value(part, "inline_data")
                if inline_data:
                    data = _get_value(inline_data, "data")
                    if isinstance(data, str) and data.strip():
                        return data.strip()
        return None


    def _extract_openai_image_b64(response: Any) -> str | None:
        data_items = _get_value(response, "data") or []
        if not data_items:
            return None

        first = data_items[0]
        b64 = _get_value(first, "b64_json")
        if isinstance(b64, str) and b64.strip():
            return b64.strip()

        return None


    def _get_value(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)
    """,
)

content = init_file.read_text(encoding="utf-8")

image_route = '''
    @bp.post("/api/ai/generate-image")
    def ai_generate_image():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or settings_store["supplier"]).strip().lower()
        prompt = str(payload.get("prompt") or "").strip()
        aspect_ratio = str(payload.get("aspectRatio") or "9:16").strip()
        model = str(payload.get("model") or "").strip() or None

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        try:
            result = build_ai_runtime(profile_registry).generate_image_for_provider(
                provider=supplier,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                model=model,
            )
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "imageDataUrl": result.image_data_url,
            "supplier": result.provider,
            "model": result.model,
        }


'''

if 'def ai_generate_image():' not in content:
    marker = '    @bp.post("/api/ai/generate-text")\n'
    if marker not in content:
        raise SystemExit("Could not find generate-text route marker.")
    content = content.replace(marker, image_route + marker, 1)


start = content.index("def _visiondirector_runtime_js_patch() -> str:")
end = content.index("\ndef _rewrite_runtime_js_urls", start)

new_patch_function = '''
def _visiondirector_runtime_js_patch() -> str:
    lines = [
        "",
        "// smx-visiondirector host AI patch.",
        "// Browser providers must use host-provided ai_profile through the Flask plugin,",
        "// not browser-owned Google/OpenAI API keys.",
        "async function __smxVisionDirectorParseScript(prompt, supplier) {",
        '  const res = await fetch("/visiondirector/api/ai/parse-script", {',
        '    method: "POST",',
        '    headers: { "Content-Type": "application/json" },',
        "    body: JSON.stringify({ prompt, supplier })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) {",
        "    throw new Error(data?.error || `VISIONDIRECTOR_PARSE_SCRIPT_FAILED: ${res.status}`);",
        "  }",
        "  return {",
        "    visuals: String(data?.visuals || \\"\\"),",
        "    narration: String(data?.narration || \\"\\")",
        "  };",
        "}",
        "",
        "async function __smxVisionDirectorGenerateImage(prompt, aspectRatio, supplier) {",
        '  const res = await fetch("/visiondirector/api/ai/generate-image", {',
        '    method: "POST",',
        '    headers: { "Content-Type": "application/json" },',
        "    body: JSON.stringify({ prompt, aspectRatio, supplier })",
        "  });",
        "  const data = await res.json().catch(() => null);",
        "  if (!res.ok) {",
        "    throw new Error(data?.error || `VISIONDIRECTOR_GENERATE_IMAGE_FAILED: ${res.status}`);",
        "  }",
        "  return data?.imageDataUrl || null;",
        "}",
        "",
        "try {",
        '  if (typeof googleProvider !== "undefined") {',
        '    googleProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, "google");',
        '    googleProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "google");',
        "  }",
        '  if (typeof openaiProvider !== "undefined") {',
        '    openaiProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, "openai");',
        '    openaiProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "openai");',
        "  }",
        "} catch (error) {",
        '  console.warn("[smx-visiondirector] Failed to install host AI provider patch", error);',
        "}",
        "",
    ]
    return "\\\\n".join(lines)

'''

content = content[:start] + new_patch_function + content[end + 1:]

init_file.write_text(content, encoding="utf-8")
print("updated generate-image host AI route and browser provider patch")

write_file(
    "tests/test_ai_generate_image_route.py",
    """
    from __future__ import annotations

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeGoogleModels:
        def __init__(self):
            self.calls = []

        def generate_content(self, *, model, contents, config):
            self.calls.append({"model": model, "contents": contents, "config": config})
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "data": "GOOGLE_IMAGE_B64"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    class FakeOpenAIImages:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return {"data": [{"b64_json": "OPENAI_IMAGE_B64"}]}


    class FakeOpenAIClient:
        def __init__(self):
            self.images = FakeOpenAIImages()


    def test_generate_image_route_uses_host_google_profile(tmp_path):
        client = FakeGoogleClient()
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "gemini-image-model",
                    "api_key": "SECRET_GOOGLE",
                    "client": client,
                }
            },
        )

        response = app.test_client().post(
            "/visiondirector/api/ai/generate-image",
            json={
                "supplier": "google",
                "prompt": "A cinematic tower",
                "aspectRatio": "16:9",
            },
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "imageDataUrl": "data:image/png;base64,GOOGLE_IMAGE_B64",
            "supplier": "google",
            "model": "gemini-image-model",
        }
        assert client.models.calls[0]["model"] == "gemini-image-model"
        assert client.models.calls[0]["config"] == {"imageConfig": {"aspectRatio": "16:9"}}
        assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


    def test_generate_image_route_uses_host_openai_profile(tmp_path):
        client = FakeOpenAIClient()
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "assistant": {
                    "provider": "openai",
                    "model": "gpt-image-1",
                    "api_key": "SECRET_OPENAI",
                    "client": client,
                }
            },
        )

        response = app.test_client().post(
            "/visiondirector/api/ai/generate-image",
            json={
                "supplier": "openai",
                "prompt": "A cinematic tower",
                "aspectRatio": "9:16",
            },
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "imageDataUrl": "data:image/png;base64,OPENAI_IMAGE_B64",
            "supplier": "openai",
            "model": "gpt-image-1",
        }
        assert client.images.calls[0]["size"] == "1024x1536"
        assert "SECRET_OPENAI" not in response.get_data(as_text=True)


    def test_served_index_js_patches_generate_image_to_host_endpoint(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path)

        response = app.test_client().get("/visiondirector/index.js")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "__smxVisionDirectorGenerateImage" in body
        assert 'fetch("/visiondirector/api/ai/generate-image"' in body
        assert 'googleProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "google")' in body
        assert 'openaiProvider.generateImage = (prompt, aspectRatio) => __smxVisionDirectorGenerateImage(prompt, aspectRatio, "openai")' in body
    """,
)

print("Patch complete: generateImage now uses host ai_profile through the plugin backend.")
