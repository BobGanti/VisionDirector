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
