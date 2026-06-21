from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


class FakeClient:
    pass


def test_credentials_status_reports_host_profiles_without_secrets(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-host-model",
                "api_key": "SECRET_GOOGLE",
                "client": FakeClient(),
            },
            "assistant": {
                "provider": "openai",
                "model": "openai-host-model",
                "api_key": "SECRET_OPENAI",
                "client": FakeClient(),
            },
        },
    )

    response = app.test_client().get("/visiondirector/api/credentials/status")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["hostManaged"] is True
    assert payload["managedBy"] == "syntaxmatrix_host"
    assert payload["google"] is True
    assert payload["openai"] is True
    assert payload["status"] == {"google": True, "openai": True}
    assert payload["providers"]["google"]["model"] == "gemini-host-model"
    assert payload["providers"]["openai"]["model"] == "openai-host-model"

    body = response.get_data(as_text=True)
    assert "SECRET_GOOGLE" not in body
    assert "SECRET_OPENAI" not in body
    assert "api_key" not in body.lower()


def test_credentials_get_supplier_exposes_status_not_key(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-host-model",
                "api_key": "SECRET_GOOGLE",
                "client": FakeClient(),
            }
        },
    )

    response = app.test_client().get("/visiondirector/api/credentials/google")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["supplier"] == "google"
    assert payload["available"] is True
    assert payload["hostManaged"] is True
    assert payload["apiKey"] == ""
    assert payload["model"] == "gemini-host-model"
    assert "SECRET_GOOGLE" not in response.get_data(as_text=True)


def test_credentials_delete_is_noop_for_host_managed_profiles(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-host-model",
                "api_key": "SECRET_GOOGLE",
                "client": FakeClient(),
            }
        },
    )

    client = app.test_client()
    delete_response = client.delete("/visiondirector/api/credentials/google")
    status_response = client.get("/visiondirector/api/credentials/status")

    assert delete_response.status_code == 200
    assert delete_response.get_json()["hostManaged"] is True
    assert delete_response.get_json()["deleted"] is False
    assert status_response.get_json()["google"] is True
    assert "SECRET_GOOGLE" not in delete_response.get_data(as_text=True)


def test_credentials_save_is_noop_for_both_route_shapes(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    client = app.test_client()
    root_response = client.post(
        "/visiondirector/api/credentials",
        json={"supplier": "google", "apiKey": "SHOULD_NOT_BE_STORED"},
    )
    supplier_response = client.post(
        "/visiondirector/api/credentials/google",
        json={"apiKey": "SHOULD_NOT_BE_STORED"},
    )

    assert root_response.status_code == 200
    assert supplier_response.status_code == 200
    assert root_response.get_json()["stored"] is False
    assert supplier_response.get_json()["stored"] is False
    assert "SHOULD_NOT_BE_STORED" not in root_response.get_data(as_text=True)
    assert "SHOULD_NOT_BE_STORED" not in supplier_response.get_data(as_text=True)


def test_public_bundle_uses_host_managed_credential_language(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "Host Provider Credentials" not in body
    assert "Paste Google API key" not in body
    assert "Paste OpenAI API key" not in body
    assert "Delete Google Key" not in body
    assert "Delete OpenAI Key" not in body
    assert "Update Keys" not in body
    assert "API Interface Credentials" not in body
    assert "Please add your Google key" not in body
    assert "Please add your OpenAI key" not in body
    assert "Paste your keys to use this deployment" not in body
