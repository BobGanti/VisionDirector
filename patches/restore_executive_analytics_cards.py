from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

if "def _executive_analytics_cards(" in text:
    print("_executive_analytics_cards already present.")
else:
    insert_before = text.find("\ndef _profile_cards")
    if insert_before < 0:
        insert_before = text.find("\ndef _group_rows")
    if insert_before < 0:
        raise SystemExit("Could not find safe insertion point for _executive_analytics_cards.")

    helper = r'''

def _executive_analytics_cards(profile_summary: dict[str, Any], usage_report: dict[str, Any]) -> str:
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

    cards = [
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
            "Provider-reported token usage without price or cost estimation.",
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

    text = text[:insert_before] + helper + text[insert_before:]
    path.write_text(text, encoding="utf-8")
    print("Restored _executive_analytics_cards helper.")
