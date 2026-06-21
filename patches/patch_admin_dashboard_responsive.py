from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
pyproject_file = ROOT / "pyproject.toml"

if not init_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/__init__.py. Run from VisionDirector root.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


write_file(
    "src/smx_visiondirector/admin_dashboard.py",
    """
    from __future__ import annotations

    from html import escape
    from typing import Any


    def render_admin_dashboard_html(
        *,
        config: dict[str, Any],
        profile_summary: dict[str, Any],
        usage_report: dict[str, Any],
    ) -> str:
        host_title = _safe(config.get("host_site_title") or "SyntaxMatrix")
        host_home_url = _safe_url(config.get("host_home_url") or "/")
        app_title = _safe(config.get("app_title") or "VisionDirector")
        logo_url = _safe_url(config.get("logo_url") or "/visiondirector/assets/logo.png")

        total_calls = _num(usage_report.get("total_calls"))
        total_input = _num(usage_report.get("total_input_tokens"))
        total_output = _num(usage_report.get("total_output_tokens"))
        total_tokens = _num(usage_report.get("total_tokens"))
        cached_tokens = _num(usage_report.get("total_cached_tokens"))
        reasoning_tokens = _num(usage_report.get("total_reasoning_tokens"))

        provider_rows = _group_rows(usage_report.get("by_provider") or {})
        model_rows = _group_rows(usage_report.get("by_model") or {})
        operation_rows = _group_rows(usage_report.get("by_operation") or {})
        event_rows = _event_rows(usage_report.get("events") or [])
        profile_cards = _profile_cards(profile_summary)

        return f'''<!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>{host_title} · {app_title} Admin</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <link rel="icon" href="{logo_url}">
      <link rel="stylesheet" href="/visiondirector/admin/static/smx-visiondirector-admin.css">
    </head>
    <body>
      <main class="smx-vd-admin-main">
        <header class="smx-vd-site-header">
          <a class="smx-vd-site-brand" href="/visiondirector/admin" aria-label="{app_title} admin home">
            <img src="{logo_url}" alt="{host_title} logo" loading="lazy">
            <span class="smx-vd-site-brand-title">{app_title} Admin</span>
          </a>

          <nav class="smx-vd-nav" aria-label="VisionDirector admin navigation">
            <a href="{host_home_url}">Back to {host_title}</a>
            <a href="/visiondirector/">Studio</a>
            <a href="/visiondirector/admin">Admin</a>
            <a href="/visiondirector/admin#usage">Token Usage</a>
            <a href="/visiondirector/admin#models">Models</a>
            <a href="/visiondirector/health">Health</a>
          </nav>

          <details class="smx-vd-mobile-menu">
            <summary aria-label="Open menu"><span class="smx-vd-mobile-menu-icon" aria-hidden="true"></span></summary>
            <div class="smx-vd-mobile-menu-panel">
              <nav class="smx-vd-mobile-menu-links" aria-label="Mobile navigation">
                <a href="{host_home_url}">Back to {host_title}</a>
                <a href="/visiondirector/">Studio</a>
                <a href="/visiondirector/admin">Admin</a>
                <a href="/visiondirector/admin#usage">Token Usage</a>
                <a href="/visiondirector/admin#models">Models</a>
                <a href="/visiondirector/health">Health</a>
              </nav>
            </div>
          </details>
        </header>

        <section class="smx-vd-hero" id="overview">
          <div>
            <p class="smx-vd-eyebrow">SyntaxMatrix Plugin Console</p>
            <h1>VisionDirector Admin Dashboard</h1>
            <p class="smx-vd-muted">Server-rendered operational dashboard for model provenance, token usage, and plugin health. No API keys, prompts, or private media are displayed.</p>
          </div>
          <div class="smx-vd-hero-actions">
            <a class="smx-vd-button" href="/visiondirector/">Open Studio</a>
            <a class="smx-vd-button is-secondary" href="/visiondirector/api/usage/report">Usage JSON</a>
          </div>
        </section>

        <section class="smx-vd-grid smx-vd-kpi-grid" aria-label="Token usage summary" id="usage">
          <article class="smx-vd-card">
            <p class="smx-vd-card-label">AI Calls</p>
            <p class="smx-vd-card-value">{total_calls}</p>
            <p class="smx-vd-card-note">Recorded plugin model calls</p>
          </article>
          <article class="smx-vd-card">
            <p class="smx-vd-card-label">Input Tokens</p>
            <p class="smx-vd-card-value">{total_input}</p>
            <p class="smx-vd-card-note">Prompt/input side</p>
          </article>
          <article class="smx-vd-card">
            <p class="smx-vd-card-label">Output Tokens</p>
            <p class="smx-vd-card-value">{total_output}</p>
            <p class="smx-vd-card-note">Generated output side</p>
          </article>
          <article class="smx-vd-card">
            <p class="smx-vd-card-label">Total Tokens</p>
            <p class="smx-vd-card-value">{total_tokens}</p>
            <p class="smx-vd-card-note">Provider-reported total</p>
          </article>
          <article class="smx-vd-card">
            <p class="smx-vd-card-label">Cached Tokens</p>
            <p class="smx-vd-card-value">{cached_tokens}</p>
            <p class="smx-vd-card-note">When provider reports it</p>
          </article>
          <article class="smx-vd-card">
            <p class="smx-vd-card-label">Reasoning Tokens</p>
            <p class="smx-vd-card-value">{reasoning_tokens}</p>
            <p class="smx-vd-card-note">When provider reports it</p>
          </article>
        </section>

        <div class="smx-vd-dashboard-shell">
          <aside class="smx-vd-section-nav" aria-label="Dashboard sections">
            <p class="smx-vd-section-nav-title">Dashboard</p>
            <nav class="smx-vd-section-nav-links">
              <a href="#usage">Usage</a>
              <a href="#providers">Providers</a>
              <a href="#operations">Operations</a>
              <a href="#models">Models</a>
              <a href="#events">Events</a>
            </nav>
          </aside>

          <div class="smx-vd-dashboard-content">
            <section class="smx-vd-panel" id="providers">
              <div class="smx-vd-panel-header">
                <div>
                  <h2>Provider Breakdown</h2>
                  <p>Token totals grouped by host-provided provider profile.</p>
                </div>
              </div>
              <div class="smx-vd-table-wrap">
                <table class="smx-vd-table">
                  <thead><tr><th>Provider</th><th>Calls</th><th>Input</th><th>Output</th><th>Total</th><th>Cached</th><th>Reasoning</th></tr></thead>
                  <tbody>{provider_rows}</tbody>
                </table>
              </div>
            </section>

            <section class="smx-vd-panel" id="operations">
              <div class="smx-vd-panel-header">
                <div>
                  <h2>Operation Breakdown</h2>
                  <p>Token totals grouped by VisionDirector operation.</p>
                </div>
              </div>
              <div class="smx-vd-table-wrap">
                <table class="smx-vd-table">
                  <thead><tr><th>Operation</th><th>Calls</th><th>Input</th><th>Output</th><th>Total</th><th>Cached</th><th>Reasoning</th></tr></thead>
                  <tbody>{operation_rows}</tbody>
                </table>
              </div>
            </section>

            <section class="smx-vd-panel" id="models">
              <div class="smx-vd-panel-header">
                <div>
                  <h2>Host Model Profiles</h2>
                  <p>Browser-safe profile metadata only. Clients and keys are never rendered.</p>
                </div>
              </div>
              <div class="smx-vd-profile-grid">{profile_cards}</div>

              <div class="smx-vd-table-wrap smx-vd-table-gap">
                <table class="smx-vd-table">
                  <thead><tr><th>Model</th><th>Calls</th><th>Input</th><th>Output</th><th>Total</th><th>Cached</th><th>Reasoning</th></tr></thead>
                  <tbody>{model_rows}</tbody>
                </table>
              </div>
            </section>

            <section class="smx-vd-panel" id="events">
              <div class="smx-vd-panel-header">
                <div>
                  <h2>Recent Token Events</h2>
                  <p>Latest normalized token events. No raw prompts or secrets are stored in this report.</p>
                </div>
              </div>
              <div class="smx-vd-table-wrap">
                <table class="smx-vd-table">
                  <thead><tr><th>Operation</th><th>Provider</th><th>Model</th><th>Status</th><th>Total</th><th>Input</th><th>Output</th></tr></thead>
                  <tbody>{event_rows}</tbody>
                </table>
              </div>
            </section>
          </div>
        </div>
      </main>
    </body>
    </html>'''


    def _group_rows(groups: dict[str, Any]) -> str:
        if not groups:
            return '<tr><td colspan="7" class="smx-vd-empty">No token usage recorded yet.</td></tr>'

        rows: list[str] = []
        for name, payload in sorted(groups.items()):
            rows.append(
                "<tr>"
                f"<td data-label='Name'>{_safe(name)}</td>"
                f"<td data-label='Calls'>{_num(payload.get('calls'))}</td>"
                f"<td data-label='Input'>{_num(payload.get('input_tokens'))}</td>"
                f"<td data-label='Output'>{_num(payload.get('output_tokens'))}</td>"
                f"<td data-label='Total'>{_num(payload.get('total_tokens'))}</td>"
                f"<td data-label='Cached'>{_num(payload.get('cached_tokens'))}</td>"
                f"<td data-label='Reasoning'>{_num(payload.get('reasoning_tokens'))}</td>"
                "</tr>"
            )
        return "".join(rows)


    def _event_rows(events: list[dict[str, Any]]) -> str:
        if not events:
            return '<tr><td colspan="7" class="smx-vd-empty">No token events recorded yet.</td></tr>'

        rows: list[str] = []
        for event in list(reversed(events))[:25]:
            status = _safe(event.get("status") or "unknown")
            rows.append(
                "<tr>"
                f"<td data-label='Operation'>{_safe(event.get('operation'))}</td>"
                f"<td data-label='Provider'>{_safe(event.get('provider'))}</td>"
                f"<td data-label='Model'>{_safe(event.get('model') or 'unknown')}</td>"
                f"<td data-label='Status'><span class='smx-vd-status is-{status}'>{status}</span></td>"
                f"<td data-label='Total'>{_num(event.get('total_tokens'))}</td>"
                f"<td data-label='Input'>{_num(event.get('input_tokens'))}</td>"
                f"<td data-label='Output'>{_num(event.get('output_tokens'))}</td>"
                "</tr>"
            )
        return "".join(rows)


    def _profile_cards(profile_summary: dict[str, Any]) -> str:
        roles = profile_summary.get("roles") or {}
        providers = profile_summary.get("providers") or {}

        cards: list[str] = []

        for role, payload in sorted(roles.items()):
            cards.append(_profile_card(title=f"Role · {role}", payload=payload))

        for provider, payload in sorted(providers.items()):
            cards.append(_profile_card(title=f"Provider · {provider}", payload=payload))

        if not cards:
            return '<div class="smx-vd-empty-card">No host AI profiles detected.</div>'

        return "".join(cards)


    def _profile_card(*, title: str, payload: dict[str, Any]) -> str:
        has_client = "Yes" if payload.get("hasClient") else "No"
        return (
            '<article class="smx-vd-profile-card">'
            f'<p class="smx-vd-profile-title">{_safe(title)}</p>'
            f'<p><strong>Provider:</strong> {_safe(payload.get("provider"))}</p>'
            f'<p><strong>Model:</strong> {_safe(payload.get("model") or "not provided")}</p>'
            f'<p><strong>Client:</strong> {_safe(has_client)}</p>'
            '</article>'
        )


    def _safe(value: Any) -> str:
        return escape(str(value if value is not None else ""), quote=True)


    def _safe_url(value: Any) -> str:
        raw = str(value if value is not None else "").strip()
        if raw.startswith(("http://", "https://", "/", "#")):
            return escape(raw, quote=True)
        return "#"


    def _num(value: Any) -> str:
        if isinstance(value, bool):
            value = 0
        try:
            return f"{int(value or 0):,}"
        except (TypeError, ValueError):
            return "0"
    """,
)

write_file(
    "src/smx_visiondirector/static/smx-visiondirector-admin.css",
    """
    :root {
      --smx-vd-bg: #f7f8fa;
      --smx-vd-surface: #ffffff;
      --smx-vd-text: #18202a;
      --smx-vd-muted: #667085;
      --smx-vd-border: #e6e8eb;
      --smx-vd-soft: #f1f5f9;
      --smx-vd-primary: #4f46e5;
      --smx-vd-primary-dark: #3730a3;
      --smx-vd-success: #027a48;
      --smx-vd-danger: #b42318;
      --smx-vd-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
      --smx-vd-radius: 18px;
    }

    * {
      box-sizing: border-box;
    }

    html {
      scroll-behavior: smooth;
    }

    body {
      margin: 0;
      background: var(--smx-vd-bg);
      color: var(--smx-vd-text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    a {
      color: var(--smx-vd-primary);
      text-decoration: none;
      font-weight: 800;
    }

    a:hover {
      color: var(--smx-vd-primary-dark);
      text-decoration: underline;
    }

    .smx-vd-admin-main {
      width: min(1440px, calc(100% - 32px));
      margin: 0 auto;
      padding: 0 0 34px;
    }

    .smx-vd-site-header {
      position: sticky;
      top: 0;
      z-index: 200;
      display: flex;
      align-items: center;
      gap: 18px;
      margin-bottom: 28px;
      padding: 12px 18px;
      background: rgba(255, 255, 255, 0.96);
      border: 1px solid var(--smx-vd-border);
      border-radius: var(--smx-vd-radius);
      box-shadow: var(--smx-vd-shadow);
      backdrop-filter: blur(16px);
    }

    .smx-vd-site-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
      color: var(--smx-vd-text);
      text-decoration: none;
    }

    .smx-vd-site-brand:hover {
      text-decoration: none;
    }

    .smx-vd-site-brand img {
      width: 38px;
      height: 38px;
      object-fit: contain;
      border-radius: 999px;
      background: var(--smx-vd-soft);
    }

    .smx-vd-site-brand-title {
      min-width: 0;
      color: var(--smx-vd-text);
      font-size: 1.05rem;
      font-weight: 900;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .smx-vd-nav {
      display: flex;
      flex: 1 1 auto;
      gap: 16px;
      flex-wrap: wrap;
      justify-content: flex-start;
      margin-left: clamp(18px, 4vw, 64px);
    }

    .smx-vd-nav a {
      color: var(--smx-vd-text);
      font-size: 0.94rem;
      white-space: nowrap;
    }

    .smx-vd-nav a:hover {
      color: var(--smx-vd-primary);
      text-decoration: none;
    }

    .smx-vd-mobile-menu {
      display: none;
    }

    .smx-vd-hero,
    .smx-vd-panel,
    .smx-vd-card,
    .smx-vd-section-nav,
    .smx-vd-profile-card,
    .smx-vd-empty-card {
      background: var(--smx-vd-surface);
      border: 1px solid var(--smx-vd-border);
      border-radius: var(--smx-vd-radius);
      box-shadow: var(--smx-vd-shadow);
    }

    .smx-vd-hero {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      margin-bottom: 18px;
      padding: clamp(18px, 3vw, 28px);
    }

    .smx-vd-eyebrow {
      margin: 0 0 8px;
      color: var(--smx-vd-primary);
      font-size: 0.78rem;
      font-weight: 950;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }

    .smx-vd-hero h1 {
      margin: 0;
      font-size: clamp(1.75rem, 4vw, 3rem);
      line-height: 1.06;
      letter-spacing: -0.045em;
    }

    .smx-vd-muted {
      max-width: 780px;
      margin: 10px 0 0;
      color: var(--smx-vd-muted);
      line-height: 1.6;
    }

    .smx-vd-hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }

    .smx-vd-button {
      display: inline-flex;
      min-height: 42px;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border: 1px solid var(--smx-vd-primary);
      border-radius: 999px;
      background: var(--smx-vd-primary);
      color: white;
      font-weight: 900;
      text-decoration: none;
      white-space: nowrap;
    }

    .smx-vd-button:hover {
      background: var(--smx-vd-primary-dark);
      color: white;
      text-decoration: none;
    }

    .smx-vd-button.is-secondary {
      background: white;
      color: var(--smx-vd-primary);
    }

    .smx-vd-grid {
      display: grid;
      gap: 14px;
    }

    .smx-vd-kpi-grid {
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      margin-bottom: 18px;
    }

    .smx-vd-card {
      min-width: 0;
      padding: 16px;
    }

    .smx-vd-card-label {
      margin: 0 0 8px;
      color: var(--smx-vd-muted);
      font-size: 0.8rem;
      font-weight: 850;
    }

    .smx-vd-card-value {
      margin: 0;
      color: var(--smx-vd-text);
      font-size: clamp(1.3rem, 2.3vw, 2rem);
      line-height: 1;
      font-weight: 950;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
    }

    .smx-vd-card-note {
      margin: 10px 0 0;
      color: var(--smx-vd-muted);
      font-size: 0.88rem;
    }

    .smx-vd-dashboard-shell {
      display: grid;
      grid-template-columns: 176px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }

    .smx-vd-dashboard-content {
      min-width: 0;
      display: grid;
      gap: 18px;
    }

    .smx-vd-section-nav {
      position: sticky;
      top: 84px;
      max-height: calc(100vh - 100px);
      overflow-y: auto;
      padding: 10px;
    }

    .smx-vd-section-nav-title {
      margin: 0 0 8px;
      padding: 0 4px;
      color: var(--smx-vd-muted);
      font-size: 0.74rem;
      font-weight: 950;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .smx-vd-section-nav-links {
      display: grid;
      gap: 4px;
    }

    .smx-vd-section-nav a {
      display: block;
      padding: 9px 10px;
      border-radius: 10px;
      color: var(--smx-vd-text);
      font-size: 0.84rem;
      line-height: 1.18;
      text-decoration: none;
    }

    .smx-vd-section-nav a:hover {
      background: var(--smx-vd-soft);
      color: var(--smx-vd-primary);
      text-decoration: none;
    }

    .smx-vd-panel {
      min-width: 0;
      padding: 18px;
      scroll-margin-top: 100px;
    }

    .smx-vd-panel-header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 14px;
    }

    .smx-vd-panel-header h2 {
      margin: 0 0 6px;
      font-size: 1.12rem;
    }

    .smx-vd-panel-header p {
      margin: 0;
      color: var(--smx-vd-muted);
      font-size: 0.93rem;
    }

    .smx-vd-profile-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
    }

    .smx-vd-profile-card,
    .smx-vd-empty-card {
      min-width: 0;
      padding: 14px;
      background: #f8fafc;
    }

    .smx-vd-profile-card p {
      margin: 6px 0 0;
      color: var(--smx-vd-muted);
      overflow-wrap: anywhere;
    }

    .smx-vd-profile-title {
      margin: 0 0 8px !important;
      color: var(--smx-vd-text) !important;
      font-weight: 950;
    }

    .smx-vd-table-gap {
      margin-top: 14px;
    }

    .smx-vd-table-wrap {
      width: 100%;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }

    .smx-vd-table {
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
    }

    .smx-vd-table th,
    .smx-vd-table td {
      padding: 12px 10px;
      border-bottom: 1px solid var(--smx-vd-border);
      text-align: left;
      vertical-align: top;
      font-size: 0.93rem;
      font-variant-numeric: tabular-nums;
    }

    .smx-vd-table th {
      color: var(--smx-vd-muted);
      font-size: 0.76rem;
      font-weight: 950;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .smx-vd-table td {
      overflow-wrap: anywhere;
    }

    .smx-vd-empty {
      color: var(--smx-vd-muted);
      text-align: center !important;
    }

    .smx-vd-status {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px 9px;
      border-radius: 999px;
      background: #fef3f2;
      color: var(--smx-vd-danger);
      font-size: 0.78rem;
      font-weight: 950;
    }

    .smx-vd-status.is-success {
      background: #ecfdf3;
      color: var(--smx-vd-success);
    }

    @media (max-width: 980px) {
      .smx-vd-dashboard-shell {
        grid-template-columns: 1fr;
      }

      .smx-vd-section-nav {
        position: static;
        max-height: none;
      }

      .smx-vd-section-nav-links {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 2px;
      }

      .smx-vd-section-nav a {
        flex: 0 0 auto;
        white-space: nowrap;
      }
    }

    @media (max-width: 760px) {
      body {
        margin: 0;
      }

      .smx-vd-admin-main {
        width: 100%;
        max-width: none;
        padding: 0 0 28px;
      }

      .smx-vd-site-header {
        width: 100%;
        min-height: 64px;
        flex-direction: row;
        justify-content: space-between;
        gap: 12px;
        margin: 0 0 16px;
        padding: 8px 14px;
        border-left: 0;
        border-right: 0;
        border-radius: 0;
      }

      .smx-vd-site-brand {
        flex: 1 1 auto;
      }

      .smx-vd-site-brand img {
        width: 42px;
        height: 42px;
        flex: 0 0 auto;
      }

      .smx-vd-site-brand-title {
        max-width: calc(100vw - 112px);
        font-size: clamp(1rem, 4.2vw, 1.25rem);
      }

      .smx-vd-site-header > .smx-vd-nav {
        display: none !important;
      }

      .smx-vd-mobile-menu {
        display: block !important;
        flex: 0 0 auto;
        margin-left: auto;
        position: relative;
      }

      .smx-vd-mobile-menu summary {
        width: 44px;
        height: 44px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--smx-vd-border);
        border-radius: 12px;
        background: var(--smx-vd-surface);
        color: var(--smx-vd-primary);
        cursor: pointer;
        list-style: none;
      }

      .smx-vd-mobile-menu summary::-webkit-details-marker {
        display: none;
      }

      .smx-vd-mobile-menu-icon {
        width: 22px;
        height: 2px;
        display: block;
        border-radius: 999px;
        background: currentColor;
        box-shadow:
          0 -7px 0 currentColor,
          0 7px 0 currentColor;
      }

      .smx-vd-mobile-menu-panel {
        position: absolute;
        top: calc(100% + 10px);
        right: 0;
        z-index: 220;
        width: min(280px, calc(100vw - 24px));
        padding: 12px;
        border: 1px solid var(--smx-vd-border);
        border-radius: 16px;
        background: var(--smx-vd-surface);
        box-shadow: var(--smx-vd-shadow);
      }

      .smx-vd-mobile-menu-links {
        display: grid;
        gap: 6px;
      }

      .smx-vd-mobile-menu-links a {
        display: block;
        padding: 10px 12px;
        border-radius: 12px;
        color: var(--smx-vd-text);
        font-weight: 850;
        text-decoration: none;
      }

      .smx-vd-mobile-menu-links a:hover {
        background: var(--smx-vd-soft);
        color: var(--smx-vd-primary);
        text-decoration: none;
      }

      .smx-vd-hero,
      .smx-vd-panel,
      .smx-vd-card {
        border-left: 0;
        border-right: 0;
        border-radius: 0;
      }

      .smx-vd-hero {
        display: grid;
        margin-bottom: 14px;
      }

      .smx-vd-hero-actions {
        justify-content: stretch;
      }

      .smx-vd-button {
        width: 100%;
      }

      .smx-vd-kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        padding: 0 12px;
      }

      .smx-vd-dashboard-shell {
        padding: 0 12px;
      }

      .smx-vd-table {
        min-width: 0;
      }

      .smx-vd-table thead {
        display: none;
      }

      .smx-vd-table,
      .smx-vd-table tbody,
      .smx-vd-table tr,
      .smx-vd-table td {
        display: block;
        width: 100%;
      }

      .smx-vd-table tr {
        padding: 10px 0;
        border-bottom: 1px solid var(--smx-vd-border);
      }

      .smx-vd-table td {
        display: flex;
        justify-content: space-between;
        gap: 14px;
        padding: 7px 0;
        border-bottom: 0;
      }

      .smx-vd-table td::before {
        content: attr(data-label);
        flex: 0 0 42%;
        color: var(--smx-vd-muted);
        font-size: 0.76rem;
        font-weight: 950;
        letter-spacing: 0.05em;
        text-transform: uppercase;
      }
    }

    @media (max-width: 430px) {
      .smx-vd-kpi-grid {
        grid-template-columns: 1fr;
      }
    }
    """,
)

pyproject = pyproject_file.read_text(encoding="utf-8")
if "[tool.setuptools.package-data]" not in pyproject:
    pyproject = pyproject.rstrip() + """

[tool.setuptools.package-data]
smx_visiondirector = ["static/*.css"]
"""
    pyproject_file.write_text(pyproject, encoding="utf-8")
    print("updated pyproject.toml package data")
else:
    print("pyproject.toml package data already present")

content = init_file.read_text(encoding="utf-8")

if "from .admin_dashboard import render_admin_dashboard_html" not in content:
    content = content.replace(
        "from .ai_profiles import AIProfileRegistry, VisionDirectorAIProfileError, build_ai_profile_registry\n",
        "from .admin_dashboard import render_admin_dashboard_html\n"
        "from .ai_profiles import AIProfileRegistry, VisionDirectorAIProfileError, build_ai_profile_registry\n",
        1,
    )

admin_routes = '''
    @bp.get("/admin")
    @bp.get("/admin/")
    def admin_dashboard():
        return Response(
            render_admin_dashboard_html(
                config=resolved_config,
                profile_summary=profile_registry.safe_summary(),
                usage_report=resolved_usage_recorder.report(),
            ),
            mimetype="text/html",
        )


    @bp.get("/admin/static/<path:filename>")
    def admin_static(filename: str):
        return send_from_directory(PACKAGE_ROOT / "static", filename)


'''

if "def admin_dashboard():" not in content:
    marker = '    @bp.get("/assets/<path:filename>")\n'
    if marker not in content:
        raise SystemExit("Could not find assets route marker.")
    content = content.replace(marker, admin_routes + marker, 1)

init_file.write_text(content, encoding="utf-8")
print("updated smx_visiondirector admin dashboard routes")

write_file(
    "tests/test_admin_dashboard.py",
    """
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
    """,
)

print("Patch complete: VisionDirector has a responsive high-performance admin dashboard.")
