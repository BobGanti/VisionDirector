from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
admin_file = Path("src/smx_visiondirector/admin_dashboard.py")

init_text = init_file.read_text(encoding="utf-8")
admin_text = admin_file.read_text(encoding="utf-8")

# 1) Add browser-safe admin reset route beside the existing API reset route.
if '@bp.post("/admin/model-overrides/<supplier>/reset")' not in init_text:
    anchor = '''    @bp.get("/api/model-map/<supplier>")
    def current_model_map(supplier: str):
        supplier = supplier.strip().lower()
        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=_model_overrides_snapshot(),
        )
        return router.clean_api_payload(supplier)


'''
    if anchor not in init_text:
        raise SystemExit("Could not find model-map route anchor.")

    admin_route = '''    @bp.post("/admin/model-overrides/<supplier>/reset")
    def admin_model_overrides_reset(supplier: str):
        guard = _require_admin_response()
        if guard is not None:
            return guard

        supplier = supplier.strip().lower()
        if supplier not in {"google", "openai"}:
            return Response("Unsupported supplier.", status=400, mimetype="text/plain")

        model_overrides_store[supplier] = {}
        return redirect(url_for(".admin_dashboard") + "#models")


'''
    init_text = init_text.replace(anchor, admin_route + anchor, 1)
    init_file.write_text(init_text, encoding="utf-8")
    print("Added browser-safe admin model reset redirect route.")
else:
    print("Admin model reset redirect route already present.")

# 2) Point dashboard forms to admin routes instead of raw JSON API routes.
admin_text = admin_text.replace(
    'action="/visiondirector/api/model-overrides/google/reset"',
    'action="/visiondirector/admin/model-overrides/google/reset"',
)
admin_text = admin_text.replace(
    'action="/visiondirector/api/model-overrides/openai/reset"',
    'action="/visiondirector/admin/model-overrides/openai/reset"',
)
admin_file.write_text(admin_text, encoding="utf-8")
print("Updated dashboard reset forms to admin redirect routes.")
