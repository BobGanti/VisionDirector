from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not init_file.exists():
    raise SystemExit("Run from VisionDirector root. Missing src/smx_visiondirector/__init__.py.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


def replace_between(source: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[:start] + replacement + source[end:]


write_file(
    "src/smx_visiondirector/model_router.py",
    """
    from __future__ import annotations

    from dataclasses import dataclass
    from typing import Any

    from .ai_profiles import AIProfileRegistry


    DEFAULT_TASK_ORDER = [
        "SCRIPT_PARSER",
        "DICTATION",
        "VOICE_ANALYZER",
        "AUTO_NARRATOR",
        "IMAGE_GEN",
        "VIDEO_GEN",
        "TTS_PREVIEW",
    ]


    @dataclass(frozen=True)
    class ResolvedModel:
        supplier: str
        task: str
        model: str
        source: str


    class ModelRouter:
        \"\"\"Resolves the current effective model for a supplier/task pair.

        Resolution order:
        1. Admin override for supplier + task
        2. Plugin default registry model
        3. Host profile model fallback

        The public model map is intentionally clean: it exposes only the current
        effective model. It does not expose previous/current comparisons.
        \"\"\"

        def __init__(
            self,
            *,
            profile_registry: AIProfileRegistry,
            registry: dict[str, Any] | None = None,
            overrides_store: dict[str, dict[str, str]] | None = None,
        ) -> None:
            self.profile_registry = profile_registry
            self.registry = registry or {}
            self.overrides_store = overrides_store if overrides_store is not None else {}

        def keys(self, supplier: str) -> list[str]:
            clean_supplier = _clean_supplier(supplier)
            registry_keys = self.registry.get("agencies") or []
            supplier_defaults = self._supplier_defaults(clean_supplier)

            ordered: list[str] = []
            for key in [*registry_keys, *DEFAULT_TASK_ORDER, *supplier_defaults.keys()]:
                clean_key = _clean_task(key)
                if clean_key and clean_key not in ordered:
                    ordered.append(clean_key)

            return ordered

        def resolve(self, supplier: str, task: str) -> ResolvedModel:
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

            profile = self.profile_registry.get_provider(clean_supplier)
            fallback = profile.model if profile else None
            return ResolvedModel(
                supplier=clean_supplier,
                task=clean_task,
                model=fallback or "",
                source="host_profile" if fallback else "missing",
            )

        def current_map(self, supplier: str) -> dict[str, dict[str, str]]:
            clean_supplier = _clean_supplier(supplier)
            current: dict[str, dict[str, str]] = {}

            for key in self.keys(clean_supplier):
                resolved = self.resolve(clean_supplier, key)
                current[key] = {
                    "supplier": resolved.supplier,
                    "task": resolved.task,
                    "model": resolved.model,
                    "source": resolved.source,
                }

            return current

        def clean_api_payload(self, supplier: str) -> dict[str, Any]:
            clean_supplier = _clean_supplier(supplier)
            current = self.current_map(clean_supplier)

            return {
                "supplier": clean_supplier,
                "keys": list(current.keys()),
                # Backwards-compatible name for the existing frontend.
                # It now means current effective models, not old defaults.
                "defaults": {
                    key: item["model"]
                    for key, item in current.items()
                },
                # Keep the old field shape but do not expose previous/current split.
                "overrides": {},
                "models": current,
            }

        def _supplier_defaults(self, supplier: str) -> dict[str, str]:
            raw = (
                self.registry.get("suppliers", {})
                .get(supplier, {})
                .get("defaults", {})
            )

            if not isinstance(raw, dict):
                return {}

            return {
                _clean_task(key): str(value).strip()
                for key, value in raw.items()
                if _clean_task(key) and str(value or "").strip()
            }

        def _supplier_overrides(self, supplier: str) -> dict[str, str]:
            raw = self.overrides_store.get(supplier, {})
            if not isinstance(raw, dict):
                return {}

            return {
                _clean_task(key): str(value).strip()
                for key, value in raw.items()
                if _clean_task(key) and str(value or "").strip()
            }


    def build_model_router(
        *,
        profile_registry: AIProfileRegistry,
        registry: dict[str, Any] | None = None,
        overrides_store: dict[str, dict[str, str]] | None = None,
    ) -> ModelRouter:
        return ModelRouter(
            profile_registry=profile_registry,
            registry=registry,
            overrides_store=overrides_store,
        )


    def _clean_supplier(value: Any) -> str:
        return str(value or "").strip().lower()


    def _clean_task(value: Any) -> str:
        return str(value or "").strip().upper()
    """,
)

content = init_file.read_text(encoding="utf-8")

if "from .model_router import build_model_router" not in content:
    content = content.replace(
        "from .ai_runtime import VisionDirectorAIExecutionError, build_ai_runtime\n",
        "from .ai_runtime import VisionDirectorAIExecutionError, build_ai_runtime\n"
        "from .model_router import build_model_router\n",
        1,
    )

get_replacement = '''
    @bp.get("/api/model-overrides/<supplier>")
    def model_overrides_get(supplier: str):
        supplier = supplier.strip().lower()
        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=model_overrides_store,
        )
        return router.clean_api_payload(supplier)


'''

post_replacement = '''
    @bp.post("/api/model-overrides/<supplier>")
    def model_overrides_post(supplier: str):
        supplier = supplier.strip().lower()
        payload = request.get_json(silent=True) or {}
        overrides = payload.get("overrides") or {}

        if not isinstance(overrides, dict):
            return {"error": "overrides must be an object"}, 400

        clean = {
            str(key).strip().upper(): str(value).strip()
            for key, value in overrides.items()
            if str(key).strip() and str(value).strip()
        }
        model_overrides_store[supplier] = clean

        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=model_overrides_store,
        )
        return router.clean_api_payload(supplier)


'''

reset_replacement = '''
    @bp.post("/api/model-overrides/<supplier>/reset")
    def model_overrides_reset(supplier: str):
        supplier = supplier.strip().lower()
        model_overrides_store[supplier] = {}

        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=model_overrides_store,
        )
        return router.clean_api_payload(supplier)


    @bp.get("/api/model-map/<supplier>")
    def current_model_map(supplier: str):
        supplier = supplier.strip().lower()
        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=model_overrides_store,
        )
        return router.clean_api_payload(supplier)


'''

content = replace_between(
    content,
    '    @bp.get("/api/model-overrides/<supplier>")\n',
    '    @bp.post("/api/model-overrides/<supplier>")\n',
    get_replacement,
)
content = replace_between(
    content,
    '    @bp.post("/api/model-overrides/<supplier>")\n',
    '    @bp.post("/api/model-overrides/<supplier>/reset")\n',
    post_replacement,
)
content = replace_between(
    content,
    '    @bp.post("/api/model-overrides/<supplier>/reset")\n',
    '    @bp.route("/api/voice-identities/<supplier>", methods=["GET", "POST"])\n',
    reset_replacement,
)

init_file.write_text(content, encoding="utf-8")
print("updated model override routes to return clean current-effective model maps")

write_file(
    "tests/test_model_router.py",
    """
    from __future__ import annotations

    from smx_visiondirector.ai_profiles import build_ai_profile_registry
    from smx_visiondirector.model_router import build_model_router


    class FakeClient:
        pass


    def test_model_router_resolves_override_default_then_host_profile():
        registry = build_ai_profile_registry(
            {
                "main": {
                    "provider": "google",
                    "model": "host-fallback-model",
                    "client": FakeClient(),
                }
            }
        )
        router = build_model_router(
            profile_registry=registry,
            registry={
                "agencies": ["SCRIPT_PARSER", "IMAGE_GEN", "VIDEO_GEN"],
                "suppliers": {
                    "google": {
                        "defaults": {
                            "SCRIPT_PARSER": "default-script-model",
                            "IMAGE_GEN": "old-image-model",
                        }
                    }
                },
            },
            overrides_store={
                "google": {
                    "IMAGE_GEN": "new-image-model",
                }
            },
        )

        assert router.resolve("google", "SCRIPT_PARSER").model == "default-script-model"
        assert router.resolve("google", "SCRIPT_PARSER").source == "default"

        assert router.resolve("google", "IMAGE_GEN").model == "new-image-model"
        assert router.resolve("google", "IMAGE_GEN").source == "override"

        assert router.resolve("google", "VIDEO_GEN").model == "host-fallback-model"
        assert router.resolve("google", "VIDEO_GEN").source == "host_profile"


    def test_clean_payload_exposes_only_current_effective_models():
        registry = build_ai_profile_registry(
            {
                "main": {
                    "provider": "google",
                    "model": "host-fallback-model",
                    "client": FakeClient(),
                }
            }
        )
        router = build_model_router(
            profile_registry=registry,
            registry={
                "agencies": ["IMAGE_GEN"],
                "suppliers": {
                    "google": {
                        "defaults": {
                            "IMAGE_GEN": "old-image-model",
                        }
                    }
                },
            },
            overrides_store={
                "google": {
                    "IMAGE_GEN": "new-image-model",
                }
            },
        )

        payload = router.clean_api_payload("google")

        assert payload["defaults"] == {"IMAGE_GEN": "new-image-model"}
        assert payload["overrides"] == {}
        assert payload["models"]["IMAGE_GEN"]["model"] == "new-image-model"
        assert "old-image-model" not in str(payload)
        assert "previous" not in str(payload).lower()
        assert "current" not in str(payload).lower()
    """,
)

write_file(
    "tests/test_clean_model_map_api.py",
    """
    from __future__ import annotations

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeClient:
        pass


    def test_model_overrides_api_returns_clean_current_model_map(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "host-google-fallback",
                    "client": FakeClient(),
                }
            },
        )

        client = app.test_client()

        update = client.post(
            "/visiondirector/api/model-overrides/google",
            json={
                "overrides": {
                    "IMAGE_GEN": "new-google-image-model",
                }
            },
        )

        assert update.status_code == 200
        payload = update.get_json()

        assert payload["supplier"] == "google"
        assert payload["defaults"]["IMAGE_GEN"] == "new-google-image-model"
        assert payload["overrides"] == {}
        assert payload["models"]["IMAGE_GEN"]["model"] == "new-google-image-model"

        body = update.get_data(as_text=True).lower()
        assert "previous" not in body
        assert "old" not in body
        assert "price" not in body
        assert "cost" not in body
        assert "currency" not in body


    def test_current_model_map_endpoint_matches_clean_contract(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "assistant": {
                    "provider": "openai",
                    "model": "host-openai-fallback",
                    "client": FakeClient(),
                }
            },
        )

        response = app.test_client().get("/visiondirector/api/model-map/openai")

        assert response.status_code == 200
        payload = response.get_json()

        assert payload["supplier"] == "openai"
        assert "SCRIPT_PARSER" in payload["keys"]
        assert payload["defaults"]["SCRIPT_PARSER"]
        assert payload["overrides"] == {}
        assert "previous" not in response.get_data(as_text=True).lower()
    """,
)

print("Patch complete: ModelRouter and clean current-effective model map API are ready.")
