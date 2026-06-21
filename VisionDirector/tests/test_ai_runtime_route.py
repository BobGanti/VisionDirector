from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


class FakeGoogleModels:
    def generate_content(self, *, model, contents):
        return {"text": f"google:{model}:{contents}"}


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


def test_ai_generate_text_route_uses_host_main_profile(tmp_path):
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
            }
        },
    )

    response = app.test_client().post(
        "/visiondirector/api/ai/generate-text",
        json={
            "role": "main",
            "prompt": "hello",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "role": "main",
        "provider": "google",
        "model": "gemini-2.5-flash",
        "text": "google:gemini-2.5-flash:hello",
    }

    assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


def test_ai_generate_text_route_reports_missing_host_profile(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path, ai_profile={})

    response = app.test_client().post(
        "/visiondirector/api/ai/generate-text",
        json={
            "role": "main",
            "prompt": "hello",
        },
    )

    assert response.status_code == 503
    assert "ai_profile['main']" in response.get_json()["error"]
