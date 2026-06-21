from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector
from smx_visiondirector.usage import extract_token_breakdown


class FakeGoogleModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if "config" in kwargs:
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
                ],
                "usageMetadata": {
                    "promptTokenCount": 11,
                    "candidatesTokenCount": 3,
                    "totalTokenCount": 14,
                    "cachedContentTokenCount": 2,
                },
            }

        return {
            "text": '{"visuals":"A city","narration":"Hello"}',
            "usageMetadata": {
                "promptTokenCount": 7,
                "candidatesTokenCount": 5,
                "totalTokenCount": 12,
                "cachedContentTokenCount": 1,
            },
        }


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


class FakeOpenAIResponses:
    def create(self, *, model, input):
        return {
            "output_text": "openai result",
            "usage": {
                "input_tokens": 13,
                "output_tokens": 8,
                "total_tokens": 21,
                "input_tokens_details": {"cached_tokens": 4},
                "output_tokens_details": {"reasoning_tokens": 2},
            },
        }


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeOpenAIResponses()


def test_extract_token_breakdown_supports_google_and_openai_shapes():
    google = extract_token_breakdown(
        {
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 4,
                "totalTokenCount": 14,
                "cachedContentTokenCount": 3,
            }
        }
    )
    assert google.as_dict() == {
        "input_tokens": 10,
        "output_tokens": 4,
        "total_tokens": 14,
        "cached_tokens": 3,
        "reasoning_tokens": 0,
    }

    openai = extract_token_breakdown(
        {
            "usage": {
                "input_tokens": 20,
                "output_tokens": 6,
                "total_tokens": 26,
                "input_tokens_details": {"cached_tokens": 5},
                "output_tokens_details": {"reasoning_tokens": 2},
            }
        }
    )
    assert openai.as_dict() == {
        "input_tokens": 20,
        "output_tokens": 6,
        "total_tokens": 26,
        "cached_tokens": 5,
        "reasoning_tokens": 2,
    }


def test_usage_report_breaks_down_tokens_without_price_or_prompt_leak(tmp_path):
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
            },
            "assistant": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "SECRET_OPENAI",
                "client": FakeOpenAIClient(),
            },
        },
    )

    client = app.test_client()

    parse_response = client.post(
        "/visiondirector/api/ai/parse-script",
        json={
            "supplier": "google",
            "prompt": "CONFIDENTIAL_PROMPT_FOR_SCRIPT",
        },
    )
    assert parse_response.status_code == 200

    image_response = client.post(
        "/visiondirector/api/ai/generate-image",
        json={
            "supplier": "google",
            "prompt": "CONFIDENTIAL_PROMPT_FOR_IMAGE",
            "aspectRatio": "16:9",
        },
    )
    assert image_response.status_code == 200

    text_response = client.post(
        "/visiondirector/api/ai/generate-text",
        json={
            "role": "assistant",
            "prompt": "CONFIDENTIAL_PROMPT_FOR_TEXT",
        },
    )
    assert text_response.status_code == 200

    report_response = client.get("/visiondirector/api/usage/report")
    assert report_response.status_code == 200

    report = report_response.get_json()
    assert report["total_calls"] == 3
    assert report["total_input_tokens"] == 31
    assert report["total_output_tokens"] == 16
    assert report["total_tokens"] == 47
    assert report["total_cached_tokens"] == 7
    assert report["total_reasoning_tokens"] == 2

    assert report["by_provider"]["google"]["calls"] == 2
    assert report["by_provider"]["google"]["total_tokens"] == 26
    assert report["by_provider"]["openai"]["calls"] == 1
    assert report["by_provider"]["openai"]["total_tokens"] == 21

    assert report["by_operation"]["parse_script"]["total_tokens"] == 12
    assert report["by_operation"]["generate_image"]["total_tokens"] == 14
    assert report["by_operation"]["generate_text"]["total_tokens"] == 21

    body = report_response.get_data(as_text=True)
    assert "SECRET_GOOGLE" not in body
    assert "SECRET_OPENAI" not in body
    assert "CONFIDENTIAL_PROMPT_FOR_SCRIPT" not in body
    assert "CONFIDENTIAL_PROMPT_FOR_IMAGE" not in body
    assert "CONFIDENTIAL_PROMPT_FOR_TEXT" not in body
    assert "price" not in body.lower()
    assert "cost" not in body.lower()
    assert "currency" not in body.lower()
