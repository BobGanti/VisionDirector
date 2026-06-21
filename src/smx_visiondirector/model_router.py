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
    """Resolves the current effective model for a supplier/task pair.

    Resolution order:
    1. Admin override for supplier + task
    2. Plugin default registry model
    3. Host profile model fallback

    The public model map is intentionally clean: it exposes only the current
    effective model. It does not expose previous/current comparisons.
    """

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
