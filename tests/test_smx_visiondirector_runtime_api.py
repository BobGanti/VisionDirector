from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


def test_index_js_rewrites_root_api_calls_under_plugin_namespace(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert 'fetch("/visiondirector/api/credentials/status"' in body
    assert 'fetch("/api/credentials/status"' not in body
    assert "`/visiondirector/api/model-overrides/${supplier}`" in body


def test_credentials_status_requires_host_provider_clients(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {"provider": "google", "api_key": "SECRET_GOOGLE"},
            "assistant": {"provider": "openai", "api_key": "SECRET_OPENAI"},
        },
    )

    response = app.test_client().get("/visiondirector/api/credentials/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["hostManaged"] is True
    assert payload["status"] == {"google": False, "openai": False}


def test_credentials_status_reflects_ready_host_profile_clients(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "host-google-model",
                "api_key": "SECRET_GOOGLE",
                "client": object(),
            },
            "assistant": {
                "provider": "openai",
                "model": "host-openai-model",
                "api_key": "SECRET_OPENAI",
                "client": object(),
            },
        },
    )

    response = app.test_client().get("/visiondirector/api/credentials/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["hostManaged"] is True
    assert payload["status"] == {"google": True, "openai": True}
    assert payload["providers"]["google"]["available"] is True
    assert payload["providers"]["openai"]["available"] is True


def test_credentials_endpoint_never_returns_api_key_value(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={"main": {"provider": "google", "api_key": "SECRET_GOOGLE"}},
    )

    response = app.test_client().get("/visiondirector/api/credentials/google")

    assert response.status_code == 200
    assert response.get_json()["apiKey"] == ""
    assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


def test_settings_runtime_api_round_trip(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)
    client = app.test_client()

    response = client.post(
        "/visiondirector/api/settings/theme",
        json={"theme": "light"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"theme": "light"}

    response = client.get("/visiondirector/api/settings/theme")
    assert response.status_code == 200
    assert response.get_json() == {"theme": "light"}


def test_model_overrides_runtime_api_reads_registry_defaults(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/api/model-overrides/google")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["supplier"] == "google"
    assert "SCRIPT_PARSER" in payload["keys"]
    assert "SCRIPT_PARSER" in payload["defaults"]


def test_voice_identities_runtime_api_round_trip(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)
    client = app.test_client()

    created = client.post(
        "/visiondirector/api/voice-identities/google",
        json={"label": "Narrator", "baseVoice": "Zephyr", "traits": "warm"},
    )

    assert created.status_code == 200
    voice = created.get_json()["voice"]
    assert voice["label"] == "NARRATOR"

    listed = client.get("/visiondirector/api/voice-identities/google")
    assert listed.status_code == 200
    assert listed.get_json()["voices"][0]["id"] == voice["id"]

    deleted = client.delete(f"/visiondirector/api/voice-identities/google/{voice['id']}")
    assert deleted.status_code == 200

    listed = client.get("/visiondirector/api/voice-identities/google")
    assert listed.get_json()["voices"] == []
