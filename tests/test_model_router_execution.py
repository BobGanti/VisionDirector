from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


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
                                        "data": "IMG_B64"
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 3,
                    "candidatesTokenCount": 2,
                    "totalTokenCount": 5,
                },
            }

        return {
            "text": '{"visuals":"clean visuals","narration":"clean narration"}',
            "usageMetadata": {
                "promptTokenCount": 4,
                "candidatesTokenCount": 3,
                "totalTokenCount": 7,
            },
        }


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


def test_parse_script_uses_host_provided_script_parser_llm(tmp_path):
    fake_client = FakeGoogleClient()
    app = Flask(__name__)

    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "host-profile-fallback-model",
                "client": fake_client,
            }
        },
    )

    client = app.test_client()

    update = client.post(
        "/visiondirector/api/model-overrides/google",
        json={
            "overrides": {
                "SCRIPT_PARSER": "current-script-model",
            }
        },
    )
    assert update.status_code == 200

    response = client.post(
        "/visiondirector/api/ai/parse-script",
        json={
            "supplier": "google",
            "prompt": "make a scene",
        },
    )

    assert response.status_code == 200
    assert fake_client.models.calls[-1]["model"] == "host-profile-fallback-model"
    assert "host-profile-fallback-model" not in response.get_data(as_text=True)


def test_generate_image_uses_current_effective_image_model(tmp_path):
    fake_client = FakeGoogleClient()
    app = Flask(__name__)

    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "host-profile-fallback-model",
                "client": fake_client,
            }
        },
    )

    client = app.test_client()

    update = client.post(
        "/visiondirector/api/model-overrides/google",
        json={
            "overrides": {
                "IMAGE_GEN": "current-image-model",
            }
        },
    )
    assert update.status_code == 200

    response = client.post(
        "/visiondirector/api/ai/generate-image",
        json={
            "supplier": "google",
            "prompt": "make an image",
            "aspectRatio": "16:9",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["model"] == "current-image-model"
    assert fake_client.models.calls[-1]["model"] == "current-image-model"
    assert "host-profile-fallback-model" not in response.get_data(as_text=True)
