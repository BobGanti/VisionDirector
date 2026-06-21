from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

start = text.find('<section class="smx-vd-panel smx-vd-admin-controls" id="admin-crud">')
end = text.find('<section class="smx-vd-panel smx-vd-executive-analytics" id="analytics">', start)

if start < 0 or end < 0:
    raise SystemExit("Could not locate patched Admin Management section.")

replacement = '''<section class="smx-vd-panel smx-vd-admin-controls" id="admin-crud">
  <div class="smx-vd-panel-header">
    <div>
      <h2>Admin Management</h2>
      <p>Operational controls for model routing, voice identities, render jobs, and usage reports.</p>
    </div>
  </div>

  <div class="smx-vd-management-grid">
    <article class="smx-vd-card smx-vd-control-card">
      <p class="smx-vd-card-label">Model Overrides</p>
      <p class="smx-vd-card-value">Manage</p>
      <p class="smx-vd-card-note">Reset supplier model overrides back to the current host/default model map.</p>
      <div class="smx-vd-control-actions">
        <form method="post" action="/visiondirector/api/model-overrides/google/reset">
          <button class="smx-vd-button smx-vd-admin-action" type="submit">Reset Google Models</button>
        </form>
        <form method="post" action="/visiondirector/api/model-overrides/openai/reset">
          <button class="smx-vd-button is-secondary smx-vd-admin-action" type="submit">Reset OpenAI Models</button>
        </form>
      </div>
    </article>

    <article class="smx-vd-card smx-vd-control-card">
      <p class="smx-vd-card-label">Voice Identities</p>
      <p class="smx-vd-card-value">Manage</p>
      <p class="smx-vd-card-note">Review saved voice identities and remove unusable voices from the voice section.</p>
      <div class="smx-vd-control-actions">
        <a class="smx-vd-button is-secondary" href="/visiondirector/admin#voices">Go to Voices</a>
      </div>
    </article>

    <article class="smx-vd-card smx-vd-control-card">
      <p class="smx-vd-card-label">Render Jobs</p>
      <p class="smx-vd-card-value">Monitor</p>
      <p class="smx-vd-card-note">Review generation jobs, errors, and provider video references.</p>
      <div class="smx-vd-control-actions">
        <a class="smx-vd-button is-secondary" href="/visiondirector/admin#render-jobs">Go to Render Jobs</a>
      </div>
    </article>
  </div>
</section>

'''

text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")
print("Repaired Admin Management section without inline JavaScript.")
