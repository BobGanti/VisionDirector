from pathlib import Path

admin_file = Path("src/smx_visiondirector/admin_dashboard.py")
css_file = Path("src/smx_visiondirector/static/smx-visiondirector-admin.css")

admin = admin_file.read_text(encoding="utf-8")
css = css_file.read_text(encoding="utf-8")

# Confirm individual token event delete.
admin = admin.replace(
    "<form method='post' action='/visiondirector/admin/usage-events/",
    "<form method='post' onsubmit=\"return confirm('Delete this token event? This cannot be undone.');\" action='/visiondirector/admin/usage-events/",
)

# Confirm clear-all token events.
admin = admin.replace(
    '<form method="post" action="/visiondirector/admin/usage-events/clear">',
    '<form method="post" action="/visiondirector/admin/usage-events/clear" onsubmit="return confirm(\'Clear all token events? This cannot be undone.\');">',
)

admin_file.write_text(admin, encoding="utf-8")

patch = r'''

/* Destructive admin action safety */
.smx-vd-row-action,
.smx-vd-admin-action,
.smx-vd-danger-action,
.smx-vd-admin-main button {
  cursor: pointer;
}

.smx-vd-danger-action {
  border-color: rgba(185, 28, 28, 0.35);
}

.smx-vd-row-action.smx-vd-danger-action {
  min-height: 30px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(185, 28, 28, 0.35);
  background: rgba(254, 226, 226, 0.95);
  color: #991b1b;
  font-weight: 800;
}

.smx-vd-row-action.smx-vd-danger-action:hover,
.smx-vd-row-action.smx-vd-danger-action:focus {
  background: #fecaca;
  outline: 2px solid rgba(185, 28, 28, 0.25);
  outline-offset: 2px;
}
'''

if "Destructive admin action safety" not in css:
    css_file.write_text(css.rstrip() + "\n" + patch + "\n", encoding="utf-8")

print("Added pointer cursor and confirmation prompts for destructive admin actions.")
