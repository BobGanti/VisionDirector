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
