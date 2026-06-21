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
                "model": "gemini-3-flash-preview",
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
        "model": "gemini-3-flash-preview",
    }

    assert client.models.calls
    assert client.models.calls[0]["model"] == "gemini-3-flash-preview"
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
