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
