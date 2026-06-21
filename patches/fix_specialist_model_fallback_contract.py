from pathlib import Path

router_file = Path("src/smx_visiondirector/model_router.py")
init_file = Path("src/smx_visiondirector/__init__.py")
test_file = Path("tests/test_model_router.py")

router = router_file.read_text(encoding="utf-8")
init_text = init_file.read_text(encoding="utf-8")
test_text = test_file.read_text(encoding="utf-8")

# 1) Router: only text/LLM tasks may fall back to the host profile model.
if "HOST_LLM_FALLBACK_TASKS" not in router:
    old = '''DEFAULT_TASK_ORDER = [
    "SCRIPT_PARSER",
    "DICTATION",
    "VOICE_ANALYZER",
    "AUTO_NARRATOR",
    "IMAGE_GEN",
    "VIDEO_GEN",
    "TTS_PREVIEW",
]
'''
    new = '''DEFAULT_TASK_ORDER = [
    "SCRIPT_PARSER",
    "DICTATION",
    "VOICE_ANALYZER",
    "AUTO_NARRATOR",
    "IMAGE_GEN",
    "VIDEO_GEN",
    "TTS_PREVIEW",
]


HOST_LLM_FALLBACK_TASKS = {
    "SCRIPT_PARSER",
    "AUTO_NARRATOR",
}
'''
    if old not in router:
        raise SystemExit("Could not find DEFAULT_TASK_ORDER block.")
    router = router.replace(old, new, 1)

router = router.replace(
    "3. Host profile model fallback",
    "3. Host profile model fallback for host-LLM text tasks only",
)

old_fallback = '''        profile = self.profile_registry.get_provider(clean_supplier)
        fallback = profile.model if profile else None
        return ResolvedModel(
            supplier=clean_supplier,
            task=clean_task,
            model=fallback or "",
            source="host_profile" if fallback else "missing",
        )
'''
new_fallback = '''        if clean_task in HOST_LLM_FALLBACK_TASKS:
            profile = self.profile_registry.get_provider(clean_supplier)
            fallback = profile.model if profile else None
            if fallback:
                return ResolvedModel(
                    supplier=clean_supplier,
                    task=clean_task,
                    model=fallback,
                    source="host_profile",
                )

        return ResolvedModel(
            supplier=clean_supplier,
            task=clean_task,
            model="",
            source="missing",
        )
'''
if old_fallback not in router:
    raise SystemExit("Could not find host-profile fallback block.")
router = router.replace(old_fallback, new_fallback, 1)

router_file.write_text(router, encoding="utf-8")
print("Updated model router: host LLM fallback is now limited to text/LLM tasks.")

# 2) Registry loader: include the actual shared frontend/backend registry path.
registry_anchor = '''        project_root / "smx_visiondirector_model_registry.json",
'''
registry_insert = '''        project_root / "smx_visiondirector_model_registry.json",
        project_root / "shared" / "model_registry.json",
        project_root / "data" / "model_registry.json",
        project_root / "data" / "model_registory.json",
'''
if 'project_root / "shared" / "model_registry.json"' not in init_text:
    if registry_anchor not in init_text:
        raise SystemExit("Could not find registry candidate anchor.")
    init_text = init_text.replace(registry_anchor, registry_insert, 1)
    init_file.write_text(init_text, encoding="utf-8")
    print("Updated registry loader to include shared/model_registry.json.")
else:
    print("Registry loader already includes shared/model_registry.json.")

# 3) Test contract: VIDEO_GEN must not fall back to host LLM.
old_test = '''    assert router.resolve("google", "VIDEO_GEN").model == "host-fallback-model"
    assert router.resolve("google", "VIDEO_GEN").source == "host_profile"
'''
new_test = '''    assert router.resolve("google", "AUTO_NARRATOR").model == "host-fallback-model"
    assert router.resolve("google", "AUTO_NARRATOR").source == "host_profile"

    assert router.resolve("google", "VIDEO_GEN").model == ""
    assert router.resolve("google", "VIDEO_GEN").source == "missing"
'''
if old_test not in test_text:
    raise SystemExit("Could not find old VIDEO_GEN fallback test assertions.")
test_text = test_text.replace(old_test, new_test, 1)
test_file.write_text(test_text, encoding="utf-8")
print("Updated model router tests for specialist capability contract.")
