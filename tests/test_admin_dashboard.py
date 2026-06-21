from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


ADMIN_TOKEN = "local-visiondirector-admin-token"


def _authorized_admin_get(client):
    login = client.post(
        "/visiondirector/admin/login",
        data={"token": ADMIN_TOKEN, "next": "/visiondirector/admin"},
    )
    assert login.status_code in {302, 303}
    return client.get("/visiondirector/admin")


class FakeGoogleModels:
    def generate_content(self, **kwargs):
        return {
            "text": '{"visuals":"A city","narration":"Hello"}',
            "usageMetadata": {
                "promptTokenCount": 9,
                "candidatesTokenCount": 4,
                "totalTokenCount": 13,
                "cachedContentTokenCount": 2,
            },
        }


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


def test_admin_dashboard_route_renders_token_usage_and_host_profiles(tmp_path):
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

    client = app.test_client()
    usage_response = client.post(
        "/visiondirector/api/ai/parse-script",
        json={"supplier": "google", "prompt": "CONFIDENTIAL_PROMPT"},
    )
    assert usage_response.status_code == 200

    response = _authorized_admin_get(client)
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert "VisionDirector Admin Dashboard" in body
    assert "Technical Diagnostics" in body
    assert "Raw provider, model, operation, and token tables" in body
    assert "Provider Breakdown" in body
    assert "Operation Breakdown" in body
    assert "Host Model Profiles" in body
    assert "gemini-2.5-flash" in body
    assert ">13<" in body or ">13</" in body

    assert "SECRET_GOOGLE" not in body
    assert "CONFIDENTIAL_PROMPT" not in body
    assert "price" not in body.lower()
    assert "cost" not in body.lower()
    assert "currency" not in body.lower()


def test_admin_dashboard_uses_desktop_nav_and_mobile_hamburger(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    client = app.test_client()
    response = _authorized_admin_get(client)
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<header class="smx-vd-site-header">' in body
    assert '<nav class="smx-vd-nav" aria-label="VisionDirector admin navigation">' in body
    assert '<details class="smx-vd-mobile-menu">' in body
    assert '<summary aria-label="Open menu">' in body
    assert 'class="smx-vd-mobile-menu-icon"' in body
    assert '<div class="smx-vd-mobile-menu-panel">' in body


def test_admin_dashboard_static_css_is_responsive_and_mobile_safe(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get(
        "/visiondirector/admin/static/smx-visiondirector-admin.css"
    )

    assert response.status_code == 200
    css = response.get_data(as_text=True)

    assert ".smx-vd-site-header" in css
    assert ".smx-vd-mobile-menu" in css
    assert ".smx-vd-mobile-menu-icon" in css
    assert "@media (max-width: 760px)" in css
    assert ".smx-vd-site-header > .smx-vd-nav" in css
    assert "display: none !important" in css
    assert "grid-template-columns: repeat(auto-fit" in css
    assert "overflow-x: auto" in css


def test_admin_dashboard_empty_state_is_clean(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    client = app.test_client()
    response = _authorized_admin_get(client)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "No token usage recorded yet." in body
    assert "No token events recorded yet." in body



def test_admin_dashboard_requires_admin_token_login(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/admin")

    assert response.status_code in {302, 303}
    assert "/visiondirector/admin/login" in response.headers["Location"]


def test_admin_login_rejects_wrong_token(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().post(
        "/visiondirector/admin/login",
        data={"token": "wrong-token", "next": "/visiondirector/admin"},
    )

    assert response.status_code == 401
    assert "Invalid admin token" in response.get_data(as_text=True)


def test_admin_login_accepts_local_scaffold_token(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    client = app.test_client()
    response = client.post(
        "/visiondirector/admin/login",
        data={"token": ADMIN_TOKEN, "next": "/visiondirector/admin"},
    )

    assert response.status_code in {302, 303}
    assert "Set-Cookie" in response.headers

    admin_response = client.get("/visiondirector/admin")
    assert admin_response.status_code == 200
    assert "VisionDirector Admin Dashboard" in admin_response.get_data(as_text=True)


def test_admin_dashboard_exposes_executive_analytics_instead_of_raw_health_json(tmp_path, monkeypatch):
    monkeypatch.setenv("SMX_VISIONDIRECTOR_ADMIN_TOKEN", "test-admin-token")

    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-2.5-flash",
                "client": FakeGoogleClient(),
            }
        },
    )

    client = app.test_client()
    login_response = client.post(
        "/visiondirector/admin/login",
        data={"token": "test-admin-token"},
    )

    assert login_response.status_code == 302

    response = client.get("/visiondirector/admin")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "Executive Analytics" in body
    assert "System Status" in body
    assert "Provider Readiness" in body
    assert "AI Activity" in body
    assert "Success Rate" in body
    assert "Most Used Operation" in body
    assert 'href="/visiondirector/admin#analytics">Analytics</a>' in body
    assert 'href="/visiondirector/health">Health</a>' not in body
    assert "Usage JSON" not in body


def test_admin_dashboard_has_logout_and_separates_technical_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("SMX_VISIONDIRECTOR_ADMIN_TOKEN", "test-admin-token")

    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-2.5-flash",
                "client": FakeGoogleClient(),
            }
        },
    )

    client = app.test_client()
    client.post(
        "/visiondirector/admin/login",
        data={"token": "test-admin-token"},
    )

    response = client.get("/visiondirector/admin")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "/visiondirector/admin/logout" in body
    assert "Logout" in body
    assert "Technical Diagnostics" in body
    assert "Raw provider, model, operation, and token tables" in body
    assert "Admin Management" in body
    assert "Model Overrides" in body
    assert "Voice Identities" in body
    assert "Render Jobs" in body


def test_admin_logout_clears_authenticated_session(tmp_path, monkeypatch):
    monkeypatch.setenv("SMX_VISIONDIRECTOR_ADMIN_TOKEN", "test-admin-token")

    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-2.5-flash",
                "client": FakeGoogleClient(),
            }
        },
    )

    client = app.test_client()

    unauthenticated = client.get("/visiondirector/admin")
    assert unauthenticated.status_code == 302
    assert "/visiondirector/admin/login" in unauthenticated.headers["Location"]

    login_response = client.post(
        "/visiondirector/admin/login",
        data={"token": "test-admin-token"},
    )
    assert login_response.status_code == 302

    authenticated = client.get("/visiondirector/admin")
    assert authenticated.status_code == 200

    logout_response = client.get("/visiondirector/admin/logout")
    assert logout_response.status_code == 302

    after_logout = client.get("/visiondirector/admin")
    assert after_logout.status_code == 302
    assert "/visiondirector/admin/login" in after_logout.headers["Location"]
