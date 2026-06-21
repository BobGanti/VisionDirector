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

    with pytest.raises(VisionDirectorAIProfileError, match="ai_profile\['main'\]"):
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
