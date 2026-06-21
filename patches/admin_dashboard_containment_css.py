from pathlib import Path

css_file = Path("src/smx_visiondirector/static/smx-visiondirector-admin.css")
text = css_file.read_text(encoding="utf-8")

patch = r'''

/* Enterprise dashboard containment patch */
.smx-vd-admin-main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 20px;
}

.smx-vd-card,
.smx-vd-panel,
.smx-vd-section,
.smx-vd-dashboard-card {
  overflow: hidden;
}

.smx-vd-table-wrap,
.smx-vd-table-wrapper,
.smx-vd-admin-table-wrap {
  width: 100%;
  overflow: auto;
  max-height: 420px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  background: #ffffff;
}

.smx-vd-card table,
.smx-vd-panel table,
.smx-vd-section table,
.smx-vd-dashboard-card table,
.smx-vd-admin-main table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

.smx-vd-admin-main thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f8fafc;
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.08);
}

.smx-vd-admin-main th,
.smx-vd-admin-main td {
  white-space: nowrap;
  vertical-align: middle;
}

.smx-vd-admin-main section:has(table) {
  overflow: hidden;
}

.smx-vd-admin-main section:has(table) table {
  display: block;
  overflow: auto;
  max-height: 420px;
}

.smx-vd-admin-main section:has(table) thead,
.smx-vd-admin-main section:has(table) tbody,
.smx-vd-admin-main section:has(table) tr {
  display: table;
  width: 100%;
  table-layout: fixed;
}

.smx-vd-admin-main section:has(table) tbody {
  display: block;
  max-height: 360px;
  overflow: auto;
}

.smx-vd-hero,
.smx-vd-site-header,
.smx-vd-card,
.smx-vd-panel,
.smx-vd-section {
  border-radius: 16px;
}

.smx-vd-hero-actions,
.smx-vd-actions,
.smx-vd-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.smx-vd-button,
.smx-vd-nav a,
.smx-vd-mobile-menu-links a,
.smx-vd-logout-link {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
}

@media (max-width: 760px) {
  .smx-vd-admin-main {
    padding: 12px;
  }

  .smx-vd-admin-main section:has(table) tbody {
    max-height: 320px;
  }

  .smx-vd-admin-main table {
    min-width: 680px;
  }
}
'''

if "Enterprise dashboard containment patch" in text:
    print("Enterprise dashboard containment CSS already present.")
else:
    css_file.write_text(text.rstrip() + "\n" + patch + "\n", encoding="utf-8")
    print("Added enterprise dashboard containment CSS.")
