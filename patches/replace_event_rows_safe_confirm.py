from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

start = text.find("def _event_rows(events: list[dict[str, Any]]) -> str:")
end = text.find("\ndef _profile_cards", start)

if start < 0 or end < 0:
    raise SystemExit("Could not locate _event_rows function block.")

replacement = """def _event_rows(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<tr><td colspan="8" class="smx-vd-empty">No token events recorded yet.</td></tr>'

    rows: list[str] = []
    for event in list(reversed(events))[:25]:
        status = _safe(event.get("status") or "unknown")
        event_id = _safe(event.get("event_id") or "")

        if event_id:
            action_html = (
                '<form method="post" '
                'onsubmit="return confirm(&quot;Delete this token event? This cannot be undone.&quot;);" '
                f'action="/visiondirector/admin/usage-events/{event_id}/delete">'
                '<button class="smx-vd-row-action smx-vd-danger-action" type="submit">Delete</button>'
                '</form>'
            )
        else:
            action_html = '<span class="smx-vd-muted">Unavailable</span>'

        rows.append(
            "<tr>"
            f"<td data-label='Operation'>{_safe(event.get('operation'))}</td>"
            f"<td data-label='Provider'>{_safe(event.get('provider'))}</td>"
            f"<td data-label='Model'>{_safe(event.get('model') or 'unknown')}</td>"
            f"<td data-label='Status'><span class='smx-vd-status is-{status}'>{status}</span></td>"
            f"<td data-label='Total'>{_num(event.get('total_tokens'))}</td>"
            f"<td data-label='Input'>{_num(event.get('input_tokens'))}</td>"
            f"<td data-label='Output'>{_num(event.get('output_tokens'))}</td>"
            f"<td data-label='Action'>{action_html}</td>"
            "</tr>"
        )
    return "".join(rows)

"""

text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")
print("Replaced broken _event_rows function with safe confirmed delete form.")
