from __future__ import annotations

from flask import Flask

import smx_visiondirector
from smx_visiondirector import setup_visiondirector


def test_setup_visiondirector_is_public_api():
    assert callable(setup_visiondirector)
    assert smx_visiondirector.DEFAULT_URL_PREFIX == "/visiondirector"


def test_setup_registers_namespaced_health_route(tmp_path):
    app = Flask(__name__)

    setup_visiondirector(
        app,
        project_root=tmp_path,
        init_schema=True,
        ai_profile={
            "main": {"provider": "google", "api_key": "secret-main"},
            "assistant": {"provider": "openai", "api_key": "secret-assistant"},
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


def test_home_serves_index_under_namespace(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "VisionDirector Elite" in body
    assert 'href="/visiondirector/index.css"' in body
    assert 'src="/visiondirector/index.js"' in body


def test_home_does_not_expose_provider_api_keys(tmp_path):
    app = Flask(__name__)

    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "api_key": "SHOULD_NOT_LEAK",
            }
        },
    )

    response = app.test_client().get("/visiondirector/")

    assert response.status_code == 200
    assert "SHOULD_NOT_LEAK" not in response.get_data(as_text=True)
