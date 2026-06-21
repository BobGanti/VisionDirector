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
                "model": "gemini-2.5-flash-image",
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
        "model": "gemini-2.5-flash-image",
    }
    assert client.models.calls[0]["model"] == "gemini-2.5-flash-image"
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
