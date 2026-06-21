from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


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

    response = client.get("/visiondirector/admin")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert "VisionDirector Admin Dashboard" in body
    assert "Token Usage" in body
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

    response = app.test_client().get("/visiondirector/admin")
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

    response = app.test_client().get("/visiondirector/admin")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "No token usage recorded yet." in body
    assert "No token events recorded yet." in body
