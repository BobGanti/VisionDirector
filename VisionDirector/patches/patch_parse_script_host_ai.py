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
            profile = self.profile_registry.require_role(role)
            return self._generate_with_profile(
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
            return self._generate_with_profile(
                profile=profile,
                prompt=prompt,
                role=profile.role or clean_provider,
                model=model,
            )

        def _generate_with_profile(
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

route_marker = '    @bp.post("/api/ai/generate-text")\n'
parse_route = r'''
    @bp.post("/api/ai/parse-script")
    def ai_parse_script():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or settings_store["supplier"]).strip().lower()
        prompt = str(payload.get("prompt") or "").strip()
        model = str(payload.get("model") or "").strip() or None

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        if not prompt:
            return {
                "visuals": "",
                "narration": "",
                "supplier": supplier,
                "model": model,
            }

        try:
            result = build_ai_runtime(profile_registry).generate_text_for_provider(
                provider=supplier,
                prompt=_script_parser_prompt(prompt),
                model=model,
            )
            parsed = _coerce_parsed_script(result.text, fallback_prompt=prompt)
        except VisionDirectorAIProfileError as exc:
            return {"error": str(exc)}, 503
        except VisionDirectorAIExecutionError as exc:
            return {"error": str(exc)}, 502

        return {
            "visuals": parsed["visuals"],
            "narration": parsed["narration"],
            "supplier": result.provider,
            "model": result.model,
        }


'''

if parse_route.strip() not in content:
    if route_marker not in content:
        raise SystemExit("Could not find AI route marker in __init__.py.")
    content = content.replace(route_marker, parse_route + route_marker, 1)

helper_marker = "def _rewrite_runtime_js_urls(js: str) -> str:"
helpers = r'''
def _script_parser_prompt(prompt: str) -> str:
    return (
        "You are VisionDirector Script Intelligence. "
        "Split the user's input into JSON with exactly two string keys: "
        "visuals and narration. Return JSON only. "
        "If the user did not provide narration, use an empty string for narration. "
        "If the user did not provide visuals, create concise cinematic visuals.\\n\\n"
        f"USER_INPUT:\\n{prompt}"
    )


def _coerce_parsed_script(text: str, *, fallback_prompt: str) -> dict[str, str]:
    raw = str(text or "").strip()
    data: dict[str, Any] = {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        extracted = _extract_json_object(raw)
        if extracted:
            try:
                data = json.loads(extracted)
            except json.JSONDecodeError:
                data = {}

    visuals = str(data.get("visuals") or fallback_prompt or "").strip()
    narration = str(data.get("narration") or "").strip()

    return {
        "visuals": visuals,
        "narration": narration,
    }


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]


def _visiondirector_runtime_js_patch() -> str:
    return r'''

// smx-visiondirector host AI patch.
// Script Intelligence must use host-provided ai_profile through the Flask plugin,
// not browser-owned Google/OpenAI API keys.
async function __smxVisionDirectorParseScript(prompt, supplier) {
  const res = await fetch("/visiondirector/api/ai/parse-script", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, supplier })
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    throw new Error(data?.error || `VISIONDIRECTOR_PARSE_SCRIPT_FAILED: ${res.status}`);
  }

  return {
    visuals: String(data?.visuals || ""),
    narration: String(data?.narration || "")
  };
}

try {
  if (typeof googleProvider !== "undefined") {
    googleProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, "google");
  }
  if (typeof openaiProvider !== "undefined") {
    openaiProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, "openai");
  }
} catch (error) {
  console.warn("[smx-visiondirector] Failed to install host AI parseScript patch", error);
}
'''


'''

if helpers.strip() not in content:
    if helper_marker not in content:
        raise SystemExit("Could not find _rewrite_runtime_js_urls marker.")
    content = content.replace(helper_marker, helpers + helper_marker, 1)

old_rewrite = r'''def _rewrite_runtime_js_urls(js: str) -> str:
    return (
        js.replace('"/api/', '"/visiondirector/api/')
        .replace("'/api/", "'/visiondirector/api/")
        .replace("`/api/", "`/visiondirector/api/")
    )
'''

new_rewrite = r'''def _rewrite_runtime_js_urls(js: str) -> str:
    rewritten = (
        js.replace('"/api/', '"/visiondirector/api/')
        .replace("'/api/", "'/visiondirector/api/")
        .replace("`/api/", "`/visiondirector/api/")
    )

    patch = _visiondirector_runtime_js_patch()
    if "__smxVisionDirectorParseScript" not in rewritten:
        rewritten = f"{rewritten}\\n{patch}\\n"

    return rewritten
'''

if old_rewrite not in content:
    raise SystemExit("Could not replace _rewrite_runtime_js_urls cleanly.")

content = content.replace(old_rewrite, new_rewrite, 1)

init_file.write_text(content, encoding="utf-8")
print("updated smx_visiondirector parse-script host AI route and JS runtime patch")

write_file(
    "tests/test_ai_parse_script_route.py",
    '''
    from __future__ import annotations

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeGoogleModels:
        def __init__(self):
            self.calls = []

        def generate_content(self, *, model, contents):
            self.calls.append({"model": model, "contents": contents})
            return {"text": '{"visuals":"A neon city at night","narration":"Welcome home."}'}


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    def test_parse_script_route_uses_host_google_profile(tmp_path):
        client = FakeGoogleClient()
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "SECRET_GOOGLE",
                    "client": client,
                }
            },
        )

        response = app.test_client().post(
            "/visiondirector/api/ai/parse-script",
            json={
                "supplier": "google",
                "prompt": "Make a cinematic intro",
            },
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "visuals": "A neon city at night",
            "narration": "Welcome home.",
            "supplier": "google",
            "model": "gemini-2.5-flash",
        }

        assert client.models.calls
        assert client.models.calls[0]["model"] == "gemini-2.5-flash"
        assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


    def test_served_index_js_patches_parse_script_to_host_endpoint(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path)

        response = app.test_client().get("/visiondirector/index.js")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "__smxVisionDirectorParseScript" in body
        assert 'googleProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, "google")' in body
        assert 'openaiProvider.parseScript = (prompt) => __smxVisionDirectorParseScript(prompt, "openai")' in body
        assert 'fetch("/visiondirector/api/ai/parse-script"' in body
    ''',
)

print("Patch complete: Script Intelligence now uses host ai_profile through the plugin backend.")
