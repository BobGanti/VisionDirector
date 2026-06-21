from pathlib import Path
import json

router_file = Path("src/smx_visiondirector/model_router.py")
router = router_file.read_text(encoding="utf-8")

# 1) Rename/strengthen the contract: LLM tasks are host-only, not fallback tasks.
router = router.replace(
    '''HOST_LLM_FALLBACK_TASKS = {
    "SCRIPT_PARSER",
    "AUTO_NARRATOR",
}
''',
    '''HOST_LLM_ONLY_TASKS = {
    "SCRIPT_PARSER",
    "AUTO_NARRATOR",
}
''',
)

router = router.replace(
    '''    Resolution order:
    1. Admin override for supplier + task
    2. Plugin default registry model
    3. Host profile model fallback for host-LLM text tasks only
''',
    '''    Resolution order:
    1. Host profile model for host-LLM-only text tasks
    2. Admin override for specialist supplier + task
    3. Specialist default registry model
''',
)

old_resolve = '''    def resolve(self, supplier: str, task: str) -> ResolvedModel:
        clean_supplier = _clean_supplier(supplier)
        clean_task = _clean_task(task)

        override = self._supplier_overrides(clean_supplier).get(clean_task)
        if override:
            return ResolvedModel(
                supplier=clean_supplier,
                task=clean_task,
                model=override,
                source="override",
            )

        default = self._supplier_defaults(clean_supplier).get(clean_task)
        if default:
            return ResolvedModel(
                supplier=clean_supplier,
                task=clean_task,
                model=default,
                source="default",
            )

        if clean_task in HOST_LLM_FALLBACK_TASKS:
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

new_resolve = '''    def resolve(self, supplier: str, task: str) -> ResolvedModel:
        clean_supplier = _clean_supplier(supplier)
        clean_task = _clean_task(task)

        if clean_task in HOST_LLM_ONLY_TASKS:
            profile = self.profile_registry.get_provider(clean_supplier)
            host_model = profile.model if profile else None
            return ResolvedModel(
                supplier=clean_supplier,
                task=clean_task,
                model=host_model or "",
                source="host_profile" if host_model else "missing",
            )

        override = self._supplier_overrides(clean_supplier).get(clean_task)
        if override:
            return ResolvedModel(
                supplier=clean_supplier,
                task=clean_task,
                model=override,
                source="override",
            )

        default = self._supplier_defaults(clean_supplier).get(clean_task)
        if default:
            return ResolvedModel(
                supplier=clean_supplier,
                task=clean_task,
                model=default,
                source="default",
            )

        return ResolvedModel(
            supplier=clean_supplier,
            task=clean_task,
            model="",
            source="missing",
        )
'''

if old_resolve not in router:
    raise SystemExit("Could not find current resolve() block. Stop; inspect before patching.")

router = router.replace(old_resolve, new_resolve, 1)
router_file.write_text(router, encoding="utf-8")
print("Updated router: LLM tasks are host-only; specialist tasks use override/default only.")


# 2) Correct specialist defaults in JSON registries.
registry_files = [
    Path("shared/model_registry.json"),
    Path("data/model_registory.json"),
]

for path in registry_files:
    if not path.exists():
        continue

    payload = json.loads(path.read_text(encoding="utf-8"))

    google_defaults = payload.setdefault("suppliers", {}).setdefault("google", {}).setdefault("defaults", {})
    openai_defaults = payload.setdefault("suppliers", {}).setdefault("openai", {}).setdefault("defaults", {})

    # LLM-only tasks must not define plugin-owned model defaults.
    google_defaults.pop("SCRIPT_PARSER", None)
    google_defaults.pop("AUTO_NARRATOR", None)
    openai_defaults.pop("SCRIPT_PARSER", None)
    openai_defaults.pop("AUTO_NARRATOR", None)

    # Specialist defaults.
    google_defaults["DICTATION"] = "chirp_3"

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Updated registry contract: {path}")


# 3) Patch direct frontend fallback registries so they do not reintroduce LLM defaults.
for path in [
    Path("services/geminiService.ts"),
    Path("services/openaiService.ts"),
    Path("index.js"),
    Path("../vision-director-sandbox/index.js"),
]:
    if not path.exists():
        continue

    text = path.read_text(encoding="utf-8")
    original = text

    text = text.replace('SCRIPT_PARSER: "gemini-3-flash-preview",\n', "")
    text = text.replace('AUTO_NARRATOR: "gemini-3-flash-preview",\n', "")
    text = text.replace('DICTATION: "gemini-3-flash-preview",', 'DICTATION: "chirp_3",')

    text = text.replace('SCRIPT_PARSER: "gpt-5-mini",\n', "")
    text = text.replace('AUTO_NARRATOR: "gpt-4.1-nano",\n', "")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"Updated frontend fallback registry: {path}")

