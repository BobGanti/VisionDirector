from __future__ import annotations

from pathlib import Path
from textwrap import dedent

admin_file = Path("src/smx_visiondirector/admin_dashboard.py")
test_file = Path("tests/test_admin_dashboard.py")
css_file = Path("src/smx_visiondirector/static/smx-visiondirector-admin.css")

content = admin_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# 1) Replace CEO-facing health/usage navigation with Analytics/Diagnostics.
# ---------------------------------------------------------------------
content = content.replace(
    '<a href="/visiondirector/health">Health</a>',
    '<a href="/visiondirector/admin#analytics">Analytics</a>',
)

content = content.replace(">Token Usage</a>", ">Technical Diagnostics</a>")
content = content.replace(">Usage</a>", ">Diagnostics</a>")

if '/visiondirector/admin/logout' not in content:
    nav_targets = [
        '<a href="/visiondirector/admin#analytics">Analytics</a>',
        '<a href="#analytics">Analytics</a>',
        '>Analytics</a>',
    ]

    inserted = False
    for target in nav_targets:
        if target in content:
            content = content.replace(
                target,
                target + '\n          <a class="smx-vd-logout-link" href="/visiondirector/admin/logout">Logout</a>',
                1,
            )
            inserted = True
            break

    if not inserted:
        raise SystemExit("Could not find an Analytics nav link to attach Logout.")

    print("Added Logout link.")
else:
    print("Logout link already present.")


# ---------------------------------------------------------------------
# 2) Add Admin Management CRUD roadmap section.
# ---------------------------------------------------------------------
crud_section = dedent(
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
    insertion_points = [
        '    <section class="smx-vd-panel smx-vd-executive-analytics"',
        '    <section class="smx-vd-executive-analytics"',
        'id="analytics"',
        'Executive Analytics',
        '    <section class="smx-vd-grid smx-vd-kpi-grid"',
        'aria-label="Token usage summary"',
    ]

    inserted = False
    for marker in insertion_points:
        idx = content.find(marker)
        if idx >= 0:
            if marker == "Executive Analytics":
                section_idx = content.rfind("<section", 0, idx)
                if section_idx >= 0:
                    idx = section_idx
            elif marker == 'id="analytics"' or marker == 'aria-label="Token usage summary"':
                section_idx = content.rfind("<section", 0, idx)
                if section_idx >= 0:
                    idx = section_idx

            content = content[:idx] + crud_section + content[idx:]
            inserted = True
            break

    if not inserted:
        raise SystemExit("Could not find a safe place to insert Admin Management section.")

    print("Added Admin Management CRUD roadmap section.")
else:
    print("Admin Management CRUD roadmap already present.")


# ---------------------------------------------------------------------
# 3) Make technical tables clearly non-CEO diagnostics.
# ---------------------------------------------------------------------
if "Raw provider, model, operation, and token tables" not in content:
    provider_heading = "<h2>Provider Breakdown</h2>"
    if provider_heading in content:
        content = content.replace(
            provider_heading,
            '<h2>Technical Diagnostics</h2>\n'
            '<p class="smx-vd-section-note">Raw provider, model, operation, and token tables for engineers and production support. CEO-level status is shown in Executive Analytics above.</p>\n'
            '<h3>Provider Breakdown</h3>',
            1,
        )
    else:
        # Fallback: insert a diagnostics note before the provider section text if the heading was already changed.
        provider_text = "Provider Breakdown"
        idx = content.find(provider_text)
        if idx >= 0:
            content = (
                content[:idx]
                + 'Technical Diagnostics</h2>\n'
                  '<p class="smx-vd-section-note">Raw provider, model, operation, and token tables for engineers and production support. CEO-level status is shown in Executive Analytics above.</p>\n'
                  '<h3>'
                + content[idx:]
            )
        else:
            print("Provider Breakdown heading not found; skipped diagnostics note insertion.")

content = content.replace("<h2>Operation Breakdown</h2>", "<h3>Operation Breakdown</h3>")
content = content.replace("<h2>Host Model Profiles</h2>", "<h3>Host Model Profiles</h3>")
content = content.replace("<h2>Recent Token Events</h2>", "<h3>Recent Token Events</h3>")

admin_file.write_text(content, encoding="utf-8")
print("Saved admin dashboard logout, diagnostics, and CRUD roadmap changes.")


# ---------------------------------------------------------------------
# 4) Add focused test.
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
    print("Added focused admin UX test.")
else:
    print("Focused admin UX test already present.")


# ---------------------------------------------------------------------
# 5) CSS polish.
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
    print("Added admin UX CSS.")
else:
    print("Admin UX CSS already present.")
