from __future__ import annotations

from pathlib import Path
from textwrap import dedent

admin_file = Path("src/smx_visiondirector/admin_dashboard.py")
test_file = Path("tests/test_admin_dashboard.py")
css_file = Path("src/smx_visiondirector/static/smx-visiondirector-admin.css")

content = admin_file.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# 1) Add Logout to top navigation if missing.
# ---------------------------------------------------------------------
if '/visiondirector/admin/logout' not in content:
    if '<a href="/visiondirector/admin#analytics">Analytics</a>' in content:
        content = content.replace(
            '<a href="/visiondirector/admin#analytics">Analytics</a>',
            '<a href="/visiondirector/admin#analytics">Analytics</a>\n'
            '          <a class="smx-vd-logout-link" href="/visiondirector/admin/logout">Logout</a>',
            1,
        )
    elif '>Analytics</a>' in content:
        content = content.replace(
            '>Analytics</a>',
            '>Analytics</a>\n'
            '          <a class="smx-vd-logout-link" href="/visiondirector/admin/logout">Logout</a>',
            1,
        )
    else:
        raise SystemExit("Could not find Analytics nav link to attach Logout.")
    print("Added Logout link to admin navigation.")
else:
    print("Logout link already present.")

# ---------------------------------------------------------------------
# 2) Stop presenting raw token data as the main CEO dashboard.
# ---------------------------------------------------------------------
content = content.replace(">Token Usage</a>", ">Technical Diagnostics</a>")
content = content.replace(">Usage</a>", ">Diagnostics</a>")

content = content.replace(
    "<h2>Provider Breakdown</h2>",
    "<h2>Technical Diagnostics</h2>\n"
    "              <p class=\"smx-vd-section-note\">Raw provider, model, operation, and token tables for engineers and production support. CEO-level status is shown in Executive Analytics above.</p>\n"
    "              <h3>Provider Breakdown</h3>",
)

content = content.replace("<h2>Operation Breakdown</h2>", "<h3>Operation Breakdown</h3>")
content = content.replace("<h2>Host Model Profiles</h2>", "<h3>Host Model Profiles</h3>")
content = content.replace("<h2>Recent Token Events</h2>", "<h3>Recent Token Events</h3>")

# ---------------------------------------------------------------------
# 3) Add visible CRUD placeholder so the admin is honest about what comes next.
# ---------------------------------------------------------------------
crud_notice = dedent(
    '''
        <section class="smx-vd-panel smx-vd-crud-roadmap" id="admin-crud">
          <div class="smx-vd-panel-header">
            <div>
              <h2>Admin Management</h2>
              <p>CRUD controls for VisionDirector configuration and operations.</p>
            </div>
          </div>
          <div class="smx-vd-management-grid">
            <article class="smx-vd-card">
              <p class="smx-vd-card-label">Model Overrides</p>
              <p class="smx-vd-card-value">Next</p>
              <p class="smx-vd-card-note">Create, update, reset, and delete model overrides per supplier and task.</p>
            </article>
            <article class="smx-vd-card">
              <p class="smx-vd-card-label">Voice Identities</p>
              <p class="smx-vd-card-value">Planned</p>
              <p class="smx-vd-card-note">Create, edit, enable, disable, and remove reusable voice identities.</p>
            </article>
            <article class="smx-vd-card">
              <p class="smx-vd-card-label">Render Jobs</p>
              <p class="smx-vd-card-value">Planned</p>
              <p class="smx-vd-card-note">View, filter, retry, archive, or delete render and generation jobs.</p>
            </article>
          </div>
        </section>

    '''
)

if 'id="admin-crud"' not in content:
    marker = '    <section class="smx-vd-panel smx-vd-executive-analytics" id="analytics">'
    if marker not in content:
        raise SystemExit("Could not find Executive Analytics section marker.")
    content = content.replace(marker, crud_notice + marker, 1)
    print("Added Admin Management CRUD roadmap section.")
else:
    print("Admin Management CRUD roadmap already present.")

admin_file.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------
# 4) Add/extend focused test.
# ---------------------------------------------------------------------
tests = test_file.read_text(encoding="utf-8")

if "test_admin_dashboard_has_logout_and_separates_technical_diagnostics" not in tests:
    tests += dedent(
        '''

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
        '''
    )
    test_file.write_text(tests, encoding="utf-8")
    print("Added admin logout/diagnostics separation test.")
else:
    print("Admin logout/diagnostics test already present.")


# ---------------------------------------------------------------------
# 5) CSS for less chaotic admin management cards and logout link.
# ---------------------------------------------------------------------
css = css_file.read_text(encoding="utf-8")

if ".smx-vd-logout-link" not in css:
    css += dedent(
        '''

        .smx-vd-logout-link {
          color: #b91c1c !important;
          font-weight: 800;
        }

        .smx-vd-section-note {
          margin: 4px 0 14px;
          color: #64748b;
          font-size: 0.88rem;
          line-height: 1.45;
        }

        .smx-vd-management-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 14px;
        }

        .smx-vd-crud-roadmap {
          border-left: 4px solid #7c3aed;
        }

        .smx-vd-panel h3 {
          margin: 12px 0 8px;
          font-size: 0.95rem;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          color: #334155;
        }
        '''
    )
    css_file.write_text(css, encoding="utf-8")
    print("Added admin logout/diagnostics CSS.")
else:
    print("Admin logout/diagnostics CSS already present.")
