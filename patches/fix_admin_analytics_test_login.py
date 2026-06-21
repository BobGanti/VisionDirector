from __future__ import annotations

from pathlib import Path
from textwrap import dedent

test_file = Path("tests/test_admin_dashboard.py")
content = test_file.read_text(encoding="utf-8")

old = dedent(
    '''
    def test_admin_dashboard_exposes_executive_analytics_instead_of_raw_health_json(tmp_path):
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

        response = app.test_client().get("/visiondirector/admin")

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
    '''
).strip()

new = dedent(
    '''
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
    '''
).strip()

if old not in content:
    raise SystemExit("Could not find the exact analytics test block to replace.")

content = content.replace(old, new, 1)
test_file.write_text(content, encoding="utf-8")

print("Updated Executive Analytics test to authenticate before loading admin dashboard.")
