from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

old = '''<section class="smx-vd-panel smx-vd-crud-roadmap" id="admin-crud">
  <div class="smx-vd-panel-header">
    <div>
      <h2>Admin Management</h2>
      <p>CRUD controls for VisionDirector configuration and operations.</p>
    </div>
  </div>
  <div class="smx-vd-management-grid">
    <article class="smx-vd-card">
      <p class="smx-vd-card-label">Model Overrides</p>
      <p class="smx-vd-card-value">Next</p>
      <p class="smx-vd-card-note">Create, update, reset, and delete model overrides per supplier and task.</p>
    </article>
    <article class="smx-vd-card">
      <p class="smx-vd-card-label">Voice Identities</p>
      <p class="smx-vd-card-value">Planned</p>
      <p class="smx-vd-card-note">Create, edit, enable, disable, and remove reusable voice identities.</p>
    </article>
    <article class="smx-vd-card">
      <p class="smx-vd-card-label">Render Jobs</p>
      <p class="smx-vd-card-value">Planned</p>
      <p class="smx-vd-card-note">View, filter, retry, archive, or delete render and generation jobs.</p>
    </article>
  </div>
</section>
'''

new = '''<section class="smx-vd-panel smx-vd-admin-controls" id="admin-crud">
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
        <button class="smx-vd-button smx-vd-admin-action" type="button" data-smx-reset-model="google">
          Reset Google Models
        </button>
        <button class="smx-vd-button is-secondary smx-vd-admin-action" type="button" data-smx-reset-model="openai">
          Reset OpenAI Models
        </button>
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

  <script>
    document.addEventListener("click", async function (event) {
      const button = event.target.closest("[data-smx-reset-model]");
      if (!button) return;

      const supplier = button.getAttribute("data-smx-reset-model");
      if (!supplier) return;

      const confirmed = window.confirm(`Reset ${supplier} model overrides?`);
      if (!confirmed) return;

      button.disabled = true;
      const previousText = button.textContent;
      button.textContent = "Resetting...";

      try {
        const response = await fetch(`/visiondirector/api/model-overrides/${supplier}/reset`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });

        if (!response.ok) {
          throw new Error(`Reset failed: ${response.status}`);
        }

        window.location.reload();
      } catch (error) {
        window.alert(error.message || "Reset failed.");
        button.disabled = false;
        button.textContent = previousText;
      }
    });
  </script>
</section>
'''

if old not in text:
    raise SystemExit("Could not find exact Admin Management roadmap block.")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Replaced roadmap Admin Management cards with real reset controls.")
