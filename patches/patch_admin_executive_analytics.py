from __future__ import annotations

from pathlib import Path
from textwrap import dedent

admin_file = Path("src/smx_visiondirector/admin_dashboard.py")
test_file = Path("tests/test_admin_dashboard.py")
css_file = Path("src/smx_visiondirector/static/smx-visiondirector-admin.css")

content = admin_file.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# 1) Replace CEO-facing Health links with Analytics anchors.
#    The /visiondirector/health JSON route remains available for technical monitoring.
# ---------------------------------------------------------------------
content = content.replace(
    '<a href="/visiondirector/health">Health</a>',
    '<a href="/visiondirector/admin#analytics">Analytics</a>',
)

content = content.replace(
    '<a class="smx-vd-button is-secondary" href="/visiondirector/api/usage/report">Usage JSON</a>',
    '<a class="smx-vd-button is-secondary" href="/visiondirector/admin#analytics">View Analytics</a>',
)

content = content.replace(
    "Server-rendered operational dashboard for model provenance, token usage, and plugin health. No API keys, prompts, or private media are displayed.",
    "CEO-friendly operational analytics for model readiness, AI activity, token usage, and production oversight. No API keys, prompts, or private media are displayed.",
)

# ---------------------------------------------------------------------
# 2) Add executive analytics cards variable.
# ---------------------------------------------------------------------
if "executive_analytics_cards = _executive_analytics_cards(" not in content:
    content = content.replace(
        "    profile_cards = _profile_cards(profile_summary)\n",
        "    profile_cards = _profile_cards(profile_summary)\n"
        "    executive_analytics_cards = _executive_analytics_cards(profile_summary, usage_report)\n",
        1,
    )

# ---------------------------------------------------------------------
# 3) Add Analytics link to dashboard side nav.
# ---------------------------------------------------------------------
if '<a href="#analytics">Analytics</a>' not in content:
    content = content.replace(
        '          <a href="#usage">Usage</a>\n',
        '          <a href="#analytics">Analytics</a>\n'
        '          <a href="#usage">Usage</a>\n',
        1,
    )

# ---------------------------------------------------------------------
# 4) Insert Executive Analytics section before technical token KPIs.
# ---------------------------------------------------------------------
analytics_section = dedent(
    '''
        <section class="smx-vd-panel smx-vd-executive-analytics" id="analytics">
          <div class="smx-vd-panel-header">
            <div>
              <h2>Executive Analytics</h2>
              <p>Plain-English operational snapshot for non-technical owners and leadership.</p>
            </div>
          </div>
          <div class="smx-vd-grid smx-vd-analytics-grid">{executive_analytics_cards}</div>
        </section>

    '''
)

if 'id="analytics"' not in content:
    marker = '    <section class="smx-vd-grid smx-vd-kpi-grid" aria-label="Token usage summary" id="usage">'
    if marker not in content:
        raise SystemExit("Could not find KPI section marker.")
    content = content.replace(marker, analytics_section + marker, 1)

# ---------------------------------------------------------------------
# 5) Add helper functions for CEO-friendly analytics.
# ---------------------------------------------------------------------
if "def _executive_analytics_cards(" not in content:
    helper = dedent(
        '''
        def _executive_analytics_cards(
            profile_summary: dict[str, Any],
            usage_report: dict[str, Any],
        ) -> str:
            events = usage_report.get("events") or []
            providers = profile_summary.get("providers") or {}

            ready_providers = sum(
                1 for payload in providers.values()
                if isinstance(payload, dict) and payload.get("hasClient")
            )
            total_providers = len(providers)

            if total_providers:
                provider_readiness = f"{ready_providers}/{total_providers} ready"
                provider_note = "Host-managed AI providers available to the plugin"
            else:
                provider_readiness = "No profiles"
                provider_note = "Host AI profiles have not been connected yet"

            total_calls = int(usage_report.get("total_calls") or 0)

            if events:
                success_count = sum(
                    1 for event in events
                    if str(event.get("status") or "").lower() == "success"
                )
                success_rate = f"{round((success_count / len(events)) * 100)}%"
                success_note = f"{success_count}/{len(events)} recent AI operations succeeded"
            else:
                success_rate = "No runs yet"
                success_note = "No AI activity has been recorded yet"

            by_operation = usage_report.get("by_operation") or {}
            if by_operation:
                busiest_operation, busiest_payload = max(
                    by_operation.items(),
                    key=lambda item: int((item[1] or {}).get("calls") or 0),
                )
                busiest_value = _safe(busiest_operation)
                busiest_note = f"{_num((busiest_payload or {}).get('calls'))} recorded calls"
            else:
                busiest_value = "No activity yet"
                busiest_note = "Operations will appear after the first AI run"

            cards = [
                ("System Status", "Online", "VisionDirector admin console is responding"),
                ("Provider Readiness", provider_readiness, provider_note),
                ("AI Activity", _num(total_calls), "Total recorded plugin AI operations"),
                ("Success Rate", success_rate, success_note),
                ("Most Used Operation", busiest_value, busiest_note),
            ]

            return "".join(
                '<article class="smx-vd-card smx-vd-analytics-card">'
                f'<p class="smx-vd-card-label">{_safe(label)}</p>'
                f'<p class="smx-vd-card-value">{value}</p>'
                f'<p class="smx-vd-card-note">{_safe(note)}</p>'
                '</article>'
                for label, value, note in cards
            )


        '''
    )

    marker = "def _profile_cards(profile_summary: dict[str, Any]) -> str:"
    if marker not in content:
        raise SystemExit("Could not find _profile_cards marker.")
    content = content.replace(marker, helper + marker, 1)

admin_file.write_text(content, encoding="utf-8")
print("Added CEO-friendly Executive Analytics section and replaced Health nav link.")


# ---------------------------------------------------------------------
# 6) Add focused admin dashboard test.
# ---------------------------------------------------------------------
tests = test_file.read_text(encoding="utf-8")

if "test_admin_dashboard_exposes_executive_analytics_instead_of_raw_health_json" not in tests:
    tests += dedent(
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
    )
    test_file.write_text(tests, encoding="utf-8")
    print("Added Executive Analytics admin dashboard test.")
else:
    print("Executive Analytics admin dashboard test already present.")


# ---------------------------------------------------------------------
# 7) Add small CSS support for analytics cards.
# ---------------------------------------------------------------------
css = css_file.read_text(encoding="utf-8")

if ".smx-vd-executive-analytics" not in css:
    css += dedent(
        '''

        .smx-vd-executive-analytics {
          margin-bottom: 18px;
        }

        .smx-vd-analytics-grid {
          grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        }

        .smx-vd-analytics-card .smx-vd-card-value {
          font-size: clamp(1.15rem, 2vw, 1.75rem);
        }
        '''
    )
    css_file.write_text(css, encoding="utf-8")
    print("Added Executive Analytics CSS.")
else:
    print("Executive Analytics CSS already present.")
