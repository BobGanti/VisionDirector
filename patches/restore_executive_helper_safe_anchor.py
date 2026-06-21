from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

if "def _executive_analytics_cards(" not in text:
    anchor = "\ndef _group_rows"
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find _group_rows anchor.")

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

    total_events = len(events)
    successful_events = total_events - len(failed_events)
    success_rate = (
        f"{round((successful_events / total_events) * 100)}%"
        if total_events
        else "No Events"
    )

    by_operation = usage_report.get("by_operation") or {}
    if by_operation:
        most_used_name, most_used_payload = max(
            by_operation.items(),
            key=lambda item: int((item[1] or {}).get("calls") or 0),
        )
        most_used_calls = int((most_used_payload or {}).get("calls") or 0)
        most_used_operation = str(most_used_name) if most_used_calls else "No Activity"
    else:
        most_used_operation = "No Activity"

    status_value = "Ready" if available_count else "Needs Setup"

    cards = [
        ("System Status", status_value, "Operational readiness based on host-managed provider availability."),
        ("Provider Readiness", f"{available_count}/{provider_count}", "Host-managed providers currently available to VisionDirector."),
        ("AI Activity", _num(total_calls), "Total recorded model calls across supported operations."),
        ("Success Rate", success_rate, "Share of recent token events that completed successfully."),
        ("Most Used Operation", most_used_operation, "Most frequent recorded AI operation."),
        ("Token Volume", _num(total_tokens), "Provider-reported token usage counts only; monetary estimates are not shown."),
        ("Operational Exceptions", _num(len(failed_events)), "Recent recorded events that did not complete successfully."),
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
    text = text[:idx] + helper + text[idx:]
    path.write_text(text, encoding="utf-8")
    print("Restored _executive_analytics_cards before _group_rows safe anchor.")
else:
    print("_executive_analytics_cards already present.")
