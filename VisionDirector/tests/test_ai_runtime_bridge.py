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
