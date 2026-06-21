from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


class FakeClient:
    pass


def test_model_overrides_api_returns_clean_current_model_map(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "host-google-fallback",
                "client": FakeClient(),
            }
        },
    )

    client = app.test_client()

    update = client.post(
        "/visiondirector/api/model-overrides/google",
        json={
            "overrides": {
                "IMAGE_GEN": "new-google-image-model",
            }
        },
    )

    assert update.status_code == 200
    payload = update.get_json()

    assert payload["supplier"] == "google"
    assert payload["defaults"]["IMAGE_GEN"] == "new-google-image-model"
    assert payload["overrides"] == {}
    assert payload["models"]["IMAGE_GEN"]["model"] == "new-google-image-model"

    body = update.get_data(as_text=True).lower()
    assert "previous" not in body
    assert "old" not in body
    assert "price" not in body
    assert "cost" not in body
    assert "currency" not in body


def test_current_model_map_endpoint_matches_clean_contract(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "assistant": {
                "provider": "openai",
                "model": "host-openai-fallback",
                "client": FakeClient(),
            }
        },
    )

    response = app.test_client().get("/visiondirector/api/model-map/openai")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["supplier"] == "openai"
    assert "SCRIPT_PARSER" in payload["keys"]
    assert payload["defaults"]["SCRIPT_PARSER"]
    assert payload["overrides"] == {}
    assert "previous" not in response.get_data(as_text=True).lower()
