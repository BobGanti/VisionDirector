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
    "src/smx_visiondirector/ai_profiles.py",
    '''
    from __future__ import annotations

    from dataclasses import dataclass, field
    from typing import Any


    class VisionDirectorAIProfileError(ValueError):
        """Raised when a required host-provided AI profile is missing or invalid."""


    @dataclass(frozen=True)
    class ProviderProfile:
        role: str | None
        provider: str
        model: str | None
        client: Any
        raw: dict[str, Any] = field(repr=False)

        @property
        def has_client(self) -> bool:
            return self.client is not None

        def safe_summary(self) -> dict[str, Any]:
            """Return browser-safe metadata only.

            Never include api_key, client objects, tokens, or raw profile values.
            """
            return {
                "role": self.role,
                "provider": self.provider,
                "model": self.model,
                "hasClient": self.has_client,
            }


    class AIProfileRegistry:
        """Normalizes host-provided VisionDirector AI profiles.

        Expected preferred shape:

            {
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "...",
                    "client": genai.Client(...),
                },
                "assistant": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "...",
                    "client": OpenAI(...),
                },
            }

        Direct provider keys are also accepted for compatibility:

            {
                "google": {...},
                "openai": {...},
            }
        """

        def __init__(self, ai_profile: dict[str, Any] | None):
            self._raw = ai_profile or {}
            self._roles: dict[str, ProviderProfile] = {}
            self._providers: dict[str, ProviderProfile] = {}
            self._normalise()

        def _normalise(self) -> None:
            if not isinstance(self._raw, dict):
                return

            for key, value in self._raw.items():
                if not isinstance(value, dict):
                    continue

                role = str(key).strip().lower()
                provider = str(value.get("provider") or "").strip().lower()

                if not provider and role not in {"main", "assistant"}:
                    provider = role

                if not provider:
                    continue

                profile = ProviderProfile(
                    role=role if role in {"main", "assistant"} else None,
                    provider=provider,
                    model=_clean_optional_string(value.get("model")),
                    client=value.get("client"),
                    raw=value,
                )

                if profile.role:
                    self._roles[profile.role] = profile

                self._providers.setdefault(provider, profile)

        def has_any(self) -> bool:
            return bool(self._roles or self._providers)

        def has_role(self, role: str) -> bool:
            return str(role).strip().lower() in self._roles

        def has_provider(self, provider: str) -> bool:
            return str(provider).strip().lower() in self._providers

        def get_role(self, role: str) -> ProviderProfile | None:
            return self._roles.get(str(role).strip().lower())

        def get_provider(self, provider: str) -> ProviderProfile | None:
            return self._providers.get(str(provider).strip().lower())

        def require_role(self, role: str) -> ProviderProfile:
            profile = self.get_role(role)
            if profile is None:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector requires host ai_profile['{role}']."
                )
            if profile.client is None:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host ai_profile['{role}']['client'] is missing."
                )
            return profile

        def require_provider(self, provider: str) -> ProviderProfile:
            profile = self.get_provider(provider)
            if profile is None:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector requires a host AI profile for provider '{provider}'."
                )
            if profile.client is None:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host AI profile for provider '{provider}' has no client."
                )
            return profile

        def safe_summary(self) -> dict[str, Any]:
            return {
                "roles": {
                    role: profile.safe_summary()
                    for role, profile in sorted(self._roles.items())
                },
                "providers": {
                    provider: profile.safe_summary()
                    for provider, profile in sorted(self._providers.items())
                },
            }


    def build_ai_profile_registry(ai_profile: dict[str, Any] | None) -> AIProfileRegistry:
        return AIProfileRegistry(ai_profile)


    def _clean_optional_string(value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None
    ''',
)


content = init_file.read_text(encoding="utf-8")

content = content.replace(
    "from .smxcp import SmxVisionDirectorScaffold, ensure_visiondirector_scaffold",
    "from .ai_profiles import AIProfileRegistry, build_ai_profile_registry\n"
    "from .smxcp import SmxVisionDirectorScaffold, ensure_visiondirector_scaffold",
)

content = content.replace(
    "            resolved_config = config or {}\n"
    "            resolved_project_root = Path(project_root or PROJECT_ROOT).resolve()\n",
    "            resolved_config = config or {}\n"
    "            resolved_project_root = Path(project_root or PROJECT_ROOT).resolve()\n"
    "            profile_registry = build_ai_profile_registry(ai_profile)\n",
)

content = content.replace(
    '''            @bp.get("/health")
            def health():
                profile = ai_profile or {}
                return {
                    "status": "ok",
                    "package": "smx-visiondirector",
                    "has_ai_profile": bool(profile),
                    "has_main_profile": "main" in profile,
                    "has_assistant_profile": "assistant" in profile,
                }
''',
    '''            @bp.get("/health")
            def health():
                return {
                    "status": "ok",
                    "package": "smx-visiondirector",
                    "has_ai_profile": profile_registry.has_any(),
                    "has_main_profile": profile_registry.has_role("main"),
                    "has_assistant_profile": profile_registry.has_role("assistant"),
                }
''',
)

content = content.replace(
    '''                    "google": _profile_has_supplier(ai_profile, "google"),
                        "openai": _profile_has_supplier(ai_profile, "openai"),
''',
    '''                    "google": profile_registry.has_provider("google"),
                        "openai": profile_registry.has_provider("openai"),
''',
)

content = content.replace(
    '''                        "available": _profile_has_supplier(ai_profile, supplier),
                        "apiKey": "",
                        "hostManaged": True,
''',
    '''                        "available": profile_registry.has_provider(supplier),
                        "apiKey": "",
                        "hostManaged": True,
''',
)

content = content.replace(
    '''            profile = ai_profile or {}
            runtime = {
                "appTitle": config.get("app_title") or "VisionDirector",
                "hostSiteTitle": config.get("host_site_title") or "SyntaxMatrix",
                "hostHomeUrl": config.get("host_home_url") or "/",
                "appHomeUrl": config.get("app_home_url") or DEFAULT_URL_PREFIX,
                "hasAiProfile": bool(profile),
                "hasMainProfile": "main" in profile,
                "hasAssistantProfile": "assistant" in profile,
            }
''',
    '''            profile_registry = build_ai_profile_registry(ai_profile)
            runtime = {
                "appTitle": config.get("app_title") or "VisionDirector",
                "hostSiteTitle": config.get("host_site_title") or "SyntaxMatrix",
                "hostHomeUrl": config.get("host_home_url") or "/",
                "appHomeUrl": config.get("app_home_url") or DEFAULT_URL_PREFIX,
                "hasAiProfile": profile_registry.has_any(),
                "hasMainProfile": profile_registry.has_role("main"),
                "hasAssistantProfile": profile_registry.has_role("assistant"),
                "aiProfile": profile_registry.safe_summary(),
            }
''',
)

content = content.replace(
    '            "SmxVisionDirectorScaffold",\n',
    '            "AIProfileRegistry",\n            "SmxVisionDirectorScaffold",\n',
)

init_file.write_text(content, encoding="utf-8")
print("updated src/smx_visiondirector/__init__.py")

write_file(
    "tests/test_ai_profile_registry.py",
    '''
    from __future__ import annotations

    import pytest

    from smx_visiondirector.ai_profiles import (
        VisionDirectorAIProfileError,
        build_ai_profile_registry,
    )


    class FakeClient:
        pass


    def test_host_main_and_assistant_profiles_are_normalized_without_leaking_secrets():
        google_client = FakeClient()
        openai_client = FakeClient()

        registry = build_ai_profile_registry(
            {
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "GOOGLE_SECRET",
                    "client": google_client,
                },
                "assistant": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "OPENAI_SECRET",
                    "client": openai_client,
                },
            }
        )

        assert registry.has_any()
        assert registry.has_role("main")
        assert registry.has_role("assistant")
        assert registry.has_provider("google")
        assert registry.has_provider("openai")

        assert registry.require_role("main").client is google_client
        assert registry.require_role("assistant").client is openai_client
        assert registry.require_provider("google").model == "gemini-2.5-flash"
        assert registry.require_provider("openai").model == "gpt-4o-mini"

        safe = str(registry.safe_summary())
        assert "GOOGLE_SECRET" not in safe
        assert "OPENAI_SECRET" not in safe
        assert "FakeClient" not in safe


    def test_assistant_profile_is_optional():
        registry = build_ai_profile_registry(
            {
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "client": FakeClient(),
                }
            }
        )

        assert registry.has_role("main")
        assert not registry.has_role("assistant")
        assert registry.has_provider("google")


    def test_direct_provider_profiles_are_supported_for_compatibility():
        registry = build_ai_profile_registry(
            {
                "google": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "client": FakeClient(),
                },
                "openai": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "client": FakeClient(),
                },
            }
        )

        assert registry.has_provider("google")
        assert registry.has_provider("openai")
        assert not registry.has_role("main")
        assert registry.require_provider("google").model == "gemini-2.5-flash"


    def test_missing_required_role_raises_clear_error():
        registry = build_ai_profile_registry({})

        with pytest.raises(VisionDirectorAIProfileError, match="ai_profile\\['main'\\]"):
            registry.require_role("main")


    def test_missing_required_client_raises_clear_error():
        registry = build_ai_profile_registry(
            {
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                }
            }
        )

        with pytest.raises(VisionDirectorAIProfileError, match="client"):
            registry.require_role("main")
    ''',
)

write_file(
    "tests/test_ai_profile_runtime_contract.py",
    '''
    from __future__ import annotations

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeClient:
        pass


    def test_health_uses_normalized_host_profiles(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "SECRET_GOOGLE",
                    "client": FakeClient(),
                },
                "assistant": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "SECRET_OPENAI",
                    "client": FakeClient(),
                },
            },
        )

        response = app.test_client().get("/visiondirector/health")

        assert response.status_code == 200
        assert response.get_json() == {
            "status": "ok",
            "package": "smx-visiondirector",
            "has_ai_profile": True,
            "has_main_profile": True,
            "has_assistant_profile": True,
        }


    def test_browser_runtime_receives_safe_profile_metadata_only(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "SECRET_GOOGLE",
                    "client": FakeClient(),
                }
            },
        )

        response = app.test_client().get("/visiondirector/")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "gemini-2.5-flash" in body
        assert "SECRET_GOOGLE" not in body
        assert "FakeClient" not in body
        assert '"hasMainProfile": true' in body
        assert '"hasAssistantProfile": false' in body
    ''',
)

print("Patch complete: VisionDirector now normalizes host-provided ai_profile safely.")
