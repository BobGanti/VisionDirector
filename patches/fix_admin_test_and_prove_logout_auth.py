from __future__ import annotations

from pathlib import Path
from textwrap import dedent

test_file = Path("tests/test_admin_dashboard.py")
content = test_file.read_text(encoding="utf-8")

# The dashboard was intentionally renamed from "Token Usage" to
# "Technical Diagnostics" because token tables are developer diagnostics,
# not CEO-facing dashboard content.
old = '    assert "Token Usage" in body\n'
new = (
    '    assert "Technical Diagnostics" in body\n'
    '    assert "Raw provider, model, operation, and token tables" in body\n'
)

if old in content:
    content = content.replace(old, new, 1)
    print("Updated old Token Usage assertion to Technical Diagnostics.")
else:
    print("Old Token Usage assertion was not found; it may already be updated.")

if "test_admin_logout_clears_authenticated_session" not in content:
    content += dedent(
        '''

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
        '''
    )
    print("Added test proving admin logout clears authenticated session.")
else:
    print("Admin logout auth test already present.")

test_file.write_text(content, encoding="utf-8")
