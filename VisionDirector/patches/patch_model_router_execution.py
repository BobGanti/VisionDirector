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


content = init_file.read_text(encoding="utf-8")

if "def _resolve_current_model(task_key: str, supplier: str) -> str | None:" not in content:
    marker = '''    bp = Blueprint("smx_visiondirector", __name__)
'''
    helper = '''    bp = Blueprint("smx_visiondirector", __name__)

    def _resolve_current_model(task_key: str, supplier: str) -> str | None:
        router = build_model_router(
            profile_registry=profile_registry,
            registry=_load_model_registry(resolved_project_root),
            overrides_store=model_overrides_store,
        )
        resolved = router.resolve(supplier, task_key)
        return resolved.model or None

'''
    if marker not in content:
        raise SystemExit("Could not find blueprint marker.")
    content = content.replace(marker, helper, 1)

old_parse = '''        model = str(payload.get("model") or "").strip() or None

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400
'''
new_parse = '''        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("SCRIPT_PARSER", supplier)
        )

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400
'''

if old_parse not in content:
    raise SystemExit("Could not find parse-script model block.")
content = content.replace(old_parse, new_parse, 1)

old_image = '''        aspect_ratio = str(payload.get("aspectRatio") or "9:16").strip()
        model = str(payload.get("model") or "").strip() or None

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400
'''
new_image = '''        aspect_ratio = str(payload.get("aspectRatio") or "9:16").strip()
        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("IMAGE_GEN", supplier)
        )

        if supplier not in {"google", "openai"}:
            return {"error": "unsupported supplier"}, 400
'''

if old_image not in content:
    raise SystemExit("Could not find generate-image model block.")
content = content.replace(old_image, new_image, 1)

init_file.write_text(content, encoding="utf-8")
print("wired parse_script and generate_image to current effective ModelRouter models")

write_file(
    "tests/test_model_router_execution.py",
    """
    from __future__ import annotations

    from flask import Flask

    from smx_visiondirector import setup_visiondirector


    class FakeGoogleModels:
        def __init__(self):
            self.calls = []

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)

            if "config" in kwargs:
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "inlineData": {
                                            "data": "IMG_B64"
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 3,
                        "candidatesTokenCount": 2,
                        "totalTokenCount": 5,
                    },
                }

            return {
                "text": '{"visuals":"clean visuals","narration":"clean narration"}',
                "usageMetadata": {
                    "promptTokenCount": 4,
                    "candidatesTokenCount": 3,
                    "totalTokenCount": 7,
                },
            }


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    def test_parse_script_uses_current_effective_script_parser_model(tmp_path):
        fake_client = FakeGoogleClient()
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "host-profile-fallback-model",
                    "client": fake_client,
                }
            },
        )

        client = app.test_client()

        update = client.post(
            "/visiondirector/api/model-overrides/google",
            json={
                "overrides": {
                    "SCRIPT_PARSER": "current-script-model",
                }
            },
        )
        assert update.status_code == 200

        response = client.post(
            "/visiondirector/api/ai/parse-script",
            json={
                "supplier": "google",
                "prompt": "make a scene",
            },
        )

        assert response.status_code == 200
        assert fake_client.models.calls[-1]["model"] == "current-script-model"
        assert "host-profile-fallback-model" not in response.get_data(as_text=True)


    def test_generate_image_uses_current_effective_image_model(tmp_path):
        fake_client = FakeGoogleClient()
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "host-profile-fallback-model",
                    "client": fake_client,
                }
            },
        )

        client = app.test_client()

        update = client.post(
            "/visiondirector/api/model-overrides/google",
            json={
                "overrides": {
                    "IMAGE_GEN": "current-image-model",
                }
            },
        )
        assert update.status_code == 200

        response = client.post(
            "/visiondirector/api/ai/generate-image",
            json={
                "supplier": "google",
                "prompt": "make an image",
                "aspectRatio": "16:9",
            },
        )

        assert response.status_code == 200
        assert response.get_json()["model"] == "current-image-model"
        assert fake_client.models.calls[-1]["model"] == "current-image-model"
        assert "host-profile-fallback-model" not in response.get_data(as_text=True)
    """,
)

print("Patch complete: execution now uses clean current-effective task models.")
