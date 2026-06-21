from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"
test_file = ROOT / "tests" / "test_google_video_extension_ref.py"

content = runtime_file.read_text(encoding="utf-8")


def replace_function(source: str, name: str, replacement: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        raise SystemExit(f"Could not find function: {name}")
    next_def = source.find("\ndef ", start + 1)
    if next_def < 0:
        next_def = len(source)
    return source[:start] + replacement.lstrip() + source[next_def:]


# 1) Add the in-memory Google extension handle store if missing.
if "_GOOGLE_VIDEO_EXTENSION_HANDLES" not in content:
    marker = "\nclass VisionDirectorAIRuntime:"
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find VisionDirectorAIRuntime insertion point.")

    handle_store = dedent(
        '''
        _GOOGLE_VIDEO_EXTENSION_HANDLES: dict[str, Any] = {}


        def _new_google_video_extension_handle(video: Any) -> str:
            handle = f"google-video-{__import__('uuid').uuid4().hex}"
            _GOOGLE_VIDEO_EXTENSION_HANDLES[handle] = video

            # Keep the dev server memory bounded. This is only an opaque runtime bridge,
            # not durable storage.
            if len(_GOOGLE_VIDEO_EXTENSION_HANDLES) > 64:
                oldest = next(iter(_GOOGLE_VIDEO_EXTENSION_HANDLES))
                _GOOGLE_VIDEO_EXTENSION_HANDLES.pop(oldest, None)

            return handle


        def _extract_google_video_extension_handle(value: Any) -> str | None:
            if isinstance(value, dict):
                raw = value.get("extensionHandle") or value.get("extension_handle")
                return str(raw).strip() if raw else None

            if isinstance(value, str) and value.startswith("google-video-"):
                return value.strip()

            return None


        '''
    ).lstrip()

    content = content[:idx] + "\n" + handle_store + content[idx:]
    print("added Google in-memory extension handle store")
else:
    print("Google extension handle store already present")


# 2) Replace the videoRef helper so first generation returns a handle to the actual provider object.
if "def _google_video_ref_for_extension(" in content:
    content = replace_function(
        content,
        "_google_video_ref_for_extension",
        dedent(
            '''
            def _google_video_ref_for_extension(*, video: Any, video_url: str | None) -> Any:
                handle = _new_google_video_extension_handle(video)
                mime_type = (
                    _get_value(video, "mimeType")
                    or _get_value(video, "mime_type")
                    or "video/mp4"
                )

                ref: dict[str, Any] = {
                    "provider": "google",
                    "extensionHandle": handle,
                    "mimeType": str(mime_type),
                    "source": "veo_generated_video_object",
                }

                name = _get_value(video, "name")
                video_id = _get_value(video, "id")
                if name:
                    ref["name"] = str(name)
                if video_id:
                    ref["id"] = str(video_id)

                return ref


            '''
        ),
    )
    print("patched _google_video_ref_for_extension")
else:
    raise SystemExit("Expected _google_video_ref_for_extension to exist from the previous patch.")


# 3) Replace the coercion helper so extension uses only the real provider object.
if "def _coerce_google_video_extension_input(" in content:
    content = replace_function(
        content,
        "_coerce_google_video_extension_input",
        dedent(
            '''
            def _coerce_google_video_extension_input(video_to_extend: Any) -> Any:
                handle = _extract_google_video_extension_handle(video_to_extend)
                if handle:
                    video = _GOOGLE_VIDEO_EXTENSION_HANDLES.get(handle)
                    if video is None:
                        raise VisionDirectorAIExecutionError(
                            "GOOGLE_EXTENSION_HANDLE_EXPIRED: generate a fresh Google video in this running server session, then extend it before restarting."
                        )
                    return video

                if video_to_extend and not isinstance(video_to_extend, (dict, str)):
                    return video_to_extend

                raise VisionDirectorAIExecutionError(
                    "GOOGLE_EXTENSION_REQUIRES_VEO_VIDEO_OBJECT: Google Veo extension requires the previous generated video object from the same running server session."
                )


            '''
        ),
    )
    print("patched _coerce_google_video_extension_input")
else:
    raise SystemExit("Expected _coerce_google_video_extension_input to exist from the previous patch.")


# 4) Ensure extension config is 720p-only and does not send aspectRatio.
old_config = '''    config = {
        "numberOfVideos": 1,
        "resolution": "720p",
        "aspectRatio": "9:16" if str(aspect_ratio) == "9:16" else "16:9",
    }
'''

new_config = '''    config = {
        "numberOfVideos": 1,
        "resolution": "720p",
    }
    if not video_to_extend:
        config["aspectRatio"] = "9:16" if str(aspect_ratio) == "9:16" else "16:9"
'''

if old_config in content:
    content = content.replace(old_config, new_config, 1)
    print("patched Google config to omit aspectRatio during extension")
else:
    print("Google config already appears extension-aware")


runtime_file.write_text(content, encoding="utf-8")


# 5) Replace focused tests with the real Python-SDK workflow contract.
test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        from pathlib import Path

        from flask import Flask

        from smx_visiondirector import setup_visiondirector


        class FakeGoogleVideoFile:
            mime_type = "video/mp4"

            def __init__(self, label="original"):
                self.label = label
                self.name = f"fake-video-{label}"

            def save(self, path):
                Path(path).write_bytes(f"FAKE_VIDEO_BYTES_{self.label}".encode("utf-8"))


        class FakeGeneratedVideo:
            def __init__(self, video):
                self.video = video


        class FakeCompletedOperation:
            done = True

            def __init__(self, video):
                self.response = type("Response", (), {"generated_videos": [FakeGeneratedVideo(video)]})()


        class FakeGoogleModels:
            def __init__(self):
                self.calls = []
                self.generated_count = 0

            def generate_videos(self, **kwargs):
                self.calls.append(kwargs)
                self.generated_count += 1
                return FakeCompletedOperation(FakeGoogleVideoFile(label=str(self.generated_count)))


        class FakeGoogleFiles:
            def download(self, *, file):
                return None


        class FakeGoogleClient:
            def __init__(self):
                self.models = FakeGoogleModels()
                self.files = FakeGoogleFiles()


        def _app(tmp_path, fake_client):
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={
                    "main": {
                        "provider": "google",
                        "model": "veo-3.1-generate-preview",
                        "client": fake_client,
                    }
                },
            )
            return app


        def test_google_video_result_returns_opaque_extension_handle_not_serialized_video(tmp_path):
            fake_client = FakeGoogleClient()
            app = _app(tmp_path, fake_client)

            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "cat playing football",
                    "narrationScript": "A cat plays football.",
                    "aspectRatio": "16:9",
                    "seconds": 8,
                },
            )

            assert response.status_code == 200
            payload = response.get_json()
            ref = payload["videoRef"]

            assert ref["provider"] == "google"
            assert ref["extensionHandle"].startswith("google-video-")
            assert ref["source"] == "veo_generated_video_object"
            assert ref["mimeType"] == "video/mp4"
            assert "videoBytes" not in ref
            assert "uri" not in ref


        def test_google_video_extension_resolves_handle_to_original_provider_object(tmp_path):
            fake_client = FakeGoogleClient()
            app = _app(tmp_path, fake_client)

            first = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "cat playing football",
                    "narrationScript": "A cat plays football.",
                    "aspectRatio": "16:9",
                    "seconds": 8,
                },
            )

            assert first.status_code == 200
            first_ref = first.get_json()["videoRef"]
            original_provider_video_object = fake_client.models.calls[0]

            second = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "The cat stopped, looked into the camera and laughed",
                    "narrationScript": "",
                    "aspectRatio": "16:9",
                    "seconds": 8,
                    "videoToExtend": first_ref,
                },
            )

            assert second.status_code == 200
            extension_call = fake_client.models.calls[-1]

            assert extension_call["video"].name == "fake-video-1"
            assert extension_call["config"] == {
                "numberOfVideos": 1,
                "resolution": "720p",
            }
            assert "aspectRatio" not in extension_call["config"]
            assert "[DIRECTOR_EXTENSION_REQUEST]" in extension_call["prompt"]


        def test_google_video_extension_rejects_serialized_video_bytes_refs(tmp_path):
            fake_client = FakeGoogleClient()
            app = _app(tmp_path, fake_client)

            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "continue the clip",
                    "narrationScript": "",
                    "aspectRatio": "16:9",
                    "seconds": 8,
                    "videoToExtend": {
                        "videoBytes": "RkFLRV9WSURFTw==",
                        "mimeType": "video/mp4",
                    },
                },
            )

            assert response.status_code == 502
            assert "GOOGLE_EXTENSION_REQUIRES_VEO_VIDEO_OBJECT" in response.get_json()["error"]
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("updated tests/test_google_video_extension_ref.py for provider-object extension workflow")
