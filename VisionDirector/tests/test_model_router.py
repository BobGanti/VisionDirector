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

    assert payload["defaults"]["IMAGE_GEN"] == "new-image-model"
    assert payload["overrides"] == {}
    assert payload["models"]["IMAGE_GEN"]["model"] == "new-image-model"

    # The clean model map may include other known VisionDirector task keys,
    # but each key must show only its current effective model.
    assert "SCRIPT_PARSER" in payload["defaults"]
    assert payload["defaults"]["SCRIPT_PARSER"] == "host-fallback-model"

    # The retired/replaced model must no longer feature anywhere.
    assert "old-image-model" not in str(payload)
    assert "previous" not in str(payload).lower()
    assert "current" not in str(payload).lower()
