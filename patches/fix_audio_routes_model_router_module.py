from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

old_transcribe = '''        model = model_router.resolve(supplier, "DICTATION").model
'''

new_transcribe = '''        model = model_router.ModelRouter(
            profile_registry=profile_registry,
            overrides_store=_model_overrides_snapshot(),
        ).resolve(supplier, "DICTATION").model
'''

old_analyze = '''        model = model_router.resolve(supplier, "VOICE_ANALYZER").model
        dictation_model = model_router.resolve(supplier, "DICTATION").model
'''

new_analyze = '''        router = model_router.ModelRouter(
            profile_registry=profile_registry,
            overrides_store=_model_overrides_snapshot(),
        )
        model = router.resolve(supplier, "VOICE_ANALYZER").model
        dictation_model = router.resolve(supplier, "DICTATION").model
'''

if old_transcribe not in content:
    raise SystemExit("Could not find transcribe model_router.resolve line.")

if old_analyze not in content:
    raise SystemExit("Could not find analyze model_router.resolve block.")

content = content.replace(old_transcribe, new_transcribe, 1)
content = content.replace(old_analyze, new_analyze, 1)

init_file.write_text(content, encoding="utf-8")
print("Fixed audio routes to instantiate model_router.ModelRouter.")
