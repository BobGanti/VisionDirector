from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
admin_file = Path("src/smx_visiondirector/admin_dashboard.py")

init_text = init_file.read_text(encoding="utf-8")
admin_text = admin_file.read_text(encoding="utf-8")

# -----------------------------
# 1) Backend helpers + admin routes
# -----------------------------
if "def _delete_usage_event_by_id(" not in init_text:
    anchor = '''    @bp.get("/api/usage/report")
    def usage_report():
        return resolved_usage_recorder.report()


'''
    if anchor not in init_text:
        raise SystemExit("Could not find usage_report route anchor.")

    routes = '''    def _delete_usage_event_by_id(event_id: str) -> bool:
        event_id = str(event_id or "").strip()
        if not event_id:
            return False

        # SQLite usage recorder.
        storage_obj = getattr(resolved_usage_recorder, "storage", None)
        config_obj = getattr(storage_obj, "config", None)
        sqlite_path = getattr(config_obj, "sqlite_path", None)
        if sqlite_path is not None:
            import sqlite3

            with sqlite3.connect(sqlite_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM visiondirector_usage_events WHERE id = ?",
                    (event_id,),
                )
                return cursor.rowcount > 0

        # JSONL usage recorder.
        path_obj = getattr(resolved_usage_recorder, "path", None)
        if path_obj is not None:
            path = Path(path_obj)
            if not path.exists():
                return False

            kept: list[str] = []
            deleted = False
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    kept.append(raw_line)
                    continue

                if str(payload.get("event_id") or "") == event_id:
                    deleted = True
                    continue
                kept.append(raw_line)

            path.write_text("\\n".join(kept) + ("\\n" if kept else ""), encoding="utf-8")
            return deleted

        # In-memory usage recorder.
        events_obj = getattr(resolved_usage_recorder, "_events", None)
        if isinstance(events_obj, list):
            before = len(events_obj)
            events_obj[:] = [
                event for event in events_obj
                if str(getattr(event, "event_id", "")) != event_id
            ]
            return len(events_obj) != before

        return False


    def _clear_usage_events() -> int:
        # SQLite usage recorder.
        storage_obj = getattr(resolved_usage_recorder, "storage", None)
        config_obj = getattr(storage_obj, "config", None)
        sqlite_path = getattr(config_obj, "sqlite_path", None)
        if sqlite_path is not None:
            import sqlite3

            with sqlite3.connect(sqlite_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM visiondirector_usage_events"
                ).fetchone()[0]
                conn.execute("DELETE FROM visiondirector_usage_events")
                return int(count or 0)

        # JSONL usage recorder.
        path_obj = getattr(resolved_usage_recorder, "path", None)
        if path_obj is not None:
            path = Path(path_obj)
            if not path.exists():
                return 0
            count = len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])
            path.write_text("", encoding="utf-8")
            return count

        # In-memory usage recorder.
        events_obj = getattr(resolved_usage_recorder, "_events", None)
        if isinstance(events_obj, list):
            count = len(events_obj)
            events_obj.clear()
            return count

        return 0


    @bp.post("/admin/usage-events/<event_id>/delete")
    def admin_usage_event_delete(event_id: str):
        guard = _require_admin_response()
        if guard is not None:
            return guard

        _delete_usage_event_by_id(event_id)
        return redirect(url_for(".admin_dashboard") + "#events")


    @bp.post("/admin/usage-events/clear")
    def admin_usage_events_clear():
        guard = _require_admin_response()
        if guard is not None:
            return guard

        _clear_usage_events()
        return redirect(url_for(".admin_dashboard") + "#events")


'''
    init_text = init_text.replace(anchor, routes + anchor, 1)
    init_file.write_text(init_text, encoding="utf-8")
    print("Added admin usage-event delete and clear routes.")
else:
    print("Admin usage-event delete/clear routes already present.")


# -----------------------------
# 2) Dashboard: add Clear All button in Recent Token Events header
# -----------------------------
old_header = '''        <section class="smx-vd-panel" id="events">
          <div class="smx-vd-panel-header">
            <div>
              <h3>Recent Token Events</h3>
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
'''

new_header = '''        <section class="smx-vd-panel" id="events">
          <div class="smx-vd-panel-header">
            <div>
              <h3>Recent Token Events</h3>
              <p>Latest normalized token events. No raw prompts or secrets are stored in this report. The dashboard shows the latest 25 events; admins can delete individual rows or clear the event log.</p>
            </div>
            <form method="post" action="/visiondirector/admin/usage-events/clear">
              <button class="smx-vd-button is-secondary smx-vd-danger-action" type="submit">Clear All Token Events</button>
            </form>
          </div>
          <div class="smx-vd-table-wrap">
            <table class="smx-vd-table">
              <thead><tr><th>Operation</th><th>Provider</th><th>Model</th><th>Status</th><th>Total</th><th>Input</th><th>Output</th><th>Action</th></tr></thead>
              <tbody>{event_rows}</tbody>
            </table>
          </div>
        </section>
'''

if old_header in admin_text:
    admin_text = admin_text.replace(old_header, new_header, 1)
    print("Added Clear All Token Events control.")
elif "Clear All Token Events" in admin_text:
    print("Clear All Token Events control already present.")
else:
    raise SystemExit("Could not find Recent Token Events section.")


# -----------------------------
# 3) Dashboard: replace _event_rows with Action column and per-row delete
# -----------------------------
start = admin_text.find("def _event_rows(events: list[dict[str, Any]]) -> str:")
end = admin_text.find("\ndef _profile_cards", start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate _event_rows function.")

new_event_rows = '''def _event_rows(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<tr><td colspan="8" class="smx-vd-empty">No token events recorded yet.</td></tr>'

    rows: list[str] = []
    for event in list(reversed(events))[:25]:
        status = _safe(event.get("status") or "unknown")
        event_id = _safe(event.get("event_id") or "")

        action_html = (
            "<form method='post' action='/visiondirector/admin/usage-events/"
            f"{event_id}/delete'>"
            "<button class='smx-vd-row-action smx-vd-danger-action' type='submit'>Delete</button>"
            "</form>"
            if event_id
            else "<span class='smx-vd-muted'>Unavailable</span>"
        )

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

'''

admin_text = admin_text[:start] + new_event_rows + admin_text[end:]
admin_file.write_text(admin_text, encoding="utf-8")
print("Added per-event Delete action to Recent Token Events.")
