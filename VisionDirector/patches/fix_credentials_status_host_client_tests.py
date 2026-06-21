from pathlib import Path

test_file = Path("tests/test_smx_visiondirector_runtime_api.py")
content = test_file.read_text(encoding="utf-8")

start = content.find("def test_credentials_status_reflects_host_profile(")
if start < 0:
    raise SystemExit("Could not find stale credentials status test.")

end = content.find("\ndef test_", start + 1)
if end < 0:
    end = len(content)

replacement = '''def test_credentials_status_requires_host_provider_clients(tmp_path):
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

'''

content = content[:start] + replacement + content[end:]
test_file.write_text(content, encoding="utf-8")

print("Updated credentials status tests to require host-provided clients.")
