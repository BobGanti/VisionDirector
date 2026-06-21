from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

start = text.find("def _executive_analytics_cards(")
end = text.find("\ndef _profile_cards", start)

if start < 0 or end < 0:
    raise SystemExit("Could not locate _executive_analytics_cards function.")

replacement = r'''def _executive_analytics_cards(profile_summary: dict[str, Any], usage_report: dict[str, Any]) -> str:
    providers = profile_summary.get("providers") or {}
    available_count = sum(
        1
        for provider in providers.values()
        if provider.get("available") or provider.get("hasClient")
    )
    provider_count = len(providers) or 2

    total_calls = int(usage_report.get("total_calls") or 0)
    total_tokens = int(usage_report.get("total_tokens") or 0)
    events = usage_report.get("events") or []
    failed_events = [
        event for event in events
        if str(event.get("status") or "").lower() not in {"ok", "success", "completed"}
    ]

    status_value = "Ready" if available_count else "Needs Setup"

    cards = [
        (
            "System Status",
            status_value,
            "Operational readiness based on host-managed provider availability.",
        ),
        (
            "Provider Readiness",
            f"{available_count}/{provider_count}",
            "Host-managed providers currently available to VisionDirector.",
        ),
        (
            "AI Activity",
            _num(total_calls),
            "Total recorded model calls across supported operations.",
        ),
        (
            "Token Volume",
            _num(total_tokens),
            "Provider-reported token usage counts only; monetary estimates are not shown.",
        ),
        (
            "Operational Exceptions",
            _num(len(failed_events)),
            "Recent recorded events that did not complete successfully.",
        ),
    ]

    rows: list[str] = []
    for label, value, note in cards:
        rows.append(
            "<article class='smx-vd-card'>"
            f"<p class='smx-vd-card-label'>{_safe(label)}</p>"
            f"<p class='smx-vd-card-value'>{_safe(value)}</p>"
            f"<p class='smx-vd-card-note'>{_safe(note)}</p>"
            "</article>"
        )

    return "".join(rows)

'''

text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")
print("Restored System Status card and removed forbidden wording.")
