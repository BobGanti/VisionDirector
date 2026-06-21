from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
frontend_file = ROOT / "index.js"

if not init_file.exists():
    raise SystemExit("Run from VisionDirector root. Missing src/smx_visiondirector/__init__.py.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


content = init_file.read_text(encoding="utf-8")

helper = '''
    def _host_provider_status_payload():
        providers = {}
        for provider_name in ("google", "openai"):
            profile = profile_registry.get_provider(provider_name)
            has_client = bool(getattr(profile, "client", None)) if profile else False
            model = str(getattr(profile, "model", "") or "") if profile else ""

            providers[provider_name] = {
                "available": has_client,
                "hostManaged": True,
                "source": "host_profile" if has_client else "missing",
                "model": model,
            }

        return {
            "google": providers["google"]["available"],
            "openai": providers["openai"]["available"],
            "hostManaged": True,
            "managedBy": "syntaxmatrix_host",
            "message": "Credentials are managed by the SyntaxMatrix host. No browser API keys are required.",
            "providers": providers,
        }


'''

if "def _host_provider_status_payload():" not in content:
    marker = '    @bp.get("/api/credentials/status")\n'
    if marker not in content:
        raise SystemExit("Could not find credentials status route marker.")
    content = content.replace(marker, helper + marker, 1)

new_credentials_block = '''
    @bp.get("/api/credentials/status")
    def credentials_status():
        return _host_provider_status_payload()


    @bp.post("/api/credentials")
    def credentials_save():
        payload = request.get_json(silent=True) or {}
        supplier = str(payload.get("supplier") or "").strip().lower()

        if supplier and supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        return {
            "ok": True,
            "hostManaged": True,
            "stored": False,
            "message": "Credentials are managed by the SyntaxMatrix host. The plugin did not store a browser API key.",
            "status": _host_provider_status_payload(),
        }


    @bp.delete("/api/credentials/<supplier>")
    def credentials_delete(supplier: str):
        supplier = supplier.strip().lower()

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400

        return {
            "ok": True,
            "hostManaged": True,
            "deleted": False,
            "message": "Credentials are managed by the SyntaxMatrix host. There is no browser API key to delete.",
            "status": _host_provider_status_payload(),
        }


    @bp.get("/api/settings/supplier")
'''

pattern = re.compile(
    r'    @bp\.get\("/api/credentials/status"\)\n.*?    @bp\.get\("/api/settings/supplier"\)\n',
    re.DOTALL,
)

content, count = pattern.subn(new_credentials_block, content, count=1)
if count != 1:
    raise SystemExit("Could not replace credentials block safely.")

init_file.write_text(content, encoding="utf-8")
print("updated credential routes to host-managed provider status")

if frontend_file.exists():
    js = frontend_file.read_text(encoding="utf-8")

    replacements = {
        "MISSING_API_KEY: Please add your Google key in API Interface Credentials.": "HOST_PROVIDER_NOT_READY: Google is not available from the SyntaxMatrix host profile.",
        "MISSING_API_KEY: Please add your OpenAI key in API Interface Credentials.": "HOST_PROVIDER_NOT_READY: OpenAI is not available from the SyntaxMatrix host profile.",
        "API Interface Credentials": "Host Provider Credentials",
        "Secure Vault": "Host Provider Vault",
        'credStatus.google ? "SAVED" : "NOT SAVED"': 'credStatus.google ? "HOST READY" : "HOST MISSING"',
        'credStatus.openai ? "SAVED" : "NOT SAVED"': 'credStatus.openai ? "HOST READY" : "HOST MISSING"',
        "Save credentials": "Refresh host status",
        "SAVE CREDENTIALS": "REFRESH HOST STATUS",
        "Delete Google key": "Google managed by host",
        "Delete OpenAI key": "OpenAI managed by host",
        "Paste your keys to use this deployment. Keys are encrypted and stored in the instance database. You can delete them any time.": "Credentials are managed by the SyntaxMatrix host. Model selection remains editable below. No browser API keys are required.",
        "Paste your keys to use this deployment. Keys are encrypted and stored in the instance database.": "Credentials are managed by the SyntaxMatrix host.",
        "You can delete them any time.": "No browser API keys are stored by this plugin.",
    }

    for old, new in replacements.items():
        js = js.replace(old, new)

    frontend_file.write_text(js, encoding="utf-8")
    print("updated frontend credential wording")
else:
    print("index.js not found; skipped frontend wording patch")

write_file(
    "tests/test_host_managed_credentials.py",
    """
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
        assert payload["providers"]["google"]["model"] == "gemini-host-model"
        assert payload["providers"]["openai"]["model"] == "openai-host-model"

        body = response.get_data(as_text=True)
        assert "SECRET_GOOGLE" not in body
        assert "SECRET_OPENAI" not in body
        assert "api_key" not in body.lower()


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

        body = delete_response.get_data(as_text=True)
        assert "SECRET_GOOGLE" not in body
        assert "api_key" not in body.lower()


    def test_credentials_save_is_noop_for_host_managed_profiles(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path)

        response = app.test_client().post(
            "/visiondirector/api/credentials",
            json={
                "supplier": "google",
                "apiKey": "SHOULD_NOT_BE_STORED",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["hostManaged"] is True
        assert payload["stored"] is False
        assert "SHOULD_NOT_BE_STORED" not in response.get_data(as_text=True)


    def test_public_bundle_uses_host_managed_credential_language(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path)

        response = app.test_client().get("/visiondirector/index.js")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "Host Provider Credentials" in body
        assert "HOST READY" in body
        assert "HOST MISSING" in body
        assert "API Interface Credentials" not in body
        assert "Please add your Google key" not in body
        assert "Please add your OpenAI key" not in body
        assert "Paste your keys to use this deployment" not in body
    """,
)

print("Patch complete: host-managed credentials are ready.")
