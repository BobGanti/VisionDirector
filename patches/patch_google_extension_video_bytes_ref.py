from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"
test_file = ROOT / "tests" / "test_google_video_extension_ref.py"

content = runtime_file.read_text(encoding="utf-8")


# 1) Make Google extension config omit aspectRatio and force extension-compatible 720p-only config.
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

if old_config not in content:
    raise SystemExit("Could not find Google video config block.")

content = content.replace(old_config, new_config, 1)
print("patched Google extension config")


# 2) Return extension-safe videoRef based on downloaded data URL bytes.
old_return = '''    return _ProviderVideoResponse(
        video_url=video_url,
        video_ref=_json_safe_video_ref(video),
        tokens=extract_token_breakdown(operation),
    )
'''

new_return = '''    return _ProviderVideoResponse(
        video_url=video_url,
        video_ref=_google_video_ref_for_extension(video=video, video_url=video_url),
        tokens=extract_token_breakdown(operation),
    )
'''

if old_return not in content:
    raise SystemExit("Could not find Google video ProviderVideoResponse return block.")

content = content.replace(old_return, new_return, 1)
print("patched Google videoRef return")


# 3) Add helper before _coerce_google_video_extension_input.
if "def _google_video_ref_for_extension(" not in content:
    marker = "\ndef _coerce_google_video_extension_input("
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _coerce_google_video_extension_input insertion point.")

    helper = dedent(
        '''
        def _google_video_ref_for_extension(*, video: Any, video_url: str | None) -> Any:
            if isinstance(video_url, str) and video_url.startswith("data:video/"):
                mime_type = video_url.split(";", 1)[0].replace("data:", "", 1) or "video/mp4"
                return {
                    "videoBytes": _strip_data_url_prefix(video_url),
                    "mimeType": mime_type,
                }

            safe = _json_safe_video_ref(video)
            if isinstance(safe, dict):
                safe.setdefault("mimeType", "video/mp4")
            return safe


        '''
    ).lstrip()

    content = content[:idx] + "\n" + helper + content[idx:]
    print("added _google_video_ref_for_extension helper")
else:
    print("_google_video_ref_for_extension helper already exists")


runtime_file.write_text(content, encoding="utf-8")


# 4) Replace focused tests so they match the extension-safe videoRef contract.
test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        from pathlib import Path

        from flask import Flask

        from smx_visiondirector import setup_visiondirector


        class FakeGoogleVideoFile:
            uri = "google://generated-video-1"
            mime_type = "video/mp4"

            def save(self, path):
                Path(path).write_bytes(b"FAKE_VIDEO_BYTES")


        class FakeGeneratedVideo:
            def __init__(self):
                self.video = FakeGoogleVideoFile()


        class FakeCompletedOperation:
            done = True

            def __init__(self):
                self.result = type("Result", (), {"generated_videos": [FakeGeneratedVideo()]})()


        class FakeGoogleModels:
            def __init__(self):
                self.calls = []

            def generate_videos(self, **kwargs):
                self.calls.append(kwargs)
                return FakeCompletedOperation()


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
                        "model": "host-google-model",
                        "client": fake_client,
                    }
                },
            )
            return app


        def test_google_video_result_returns_extension_safe_video_bytes_ref(tmp_path):
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
            assert payload["videoRef"]["mimeType"] == "video/mp4"
            assert payload["videoRef"]["videoBytes"]
            assert "uri" not in payload["videoRef"]


        def test_google_video_extension_uses_video_bytes_ref_and_omits_aspect_ratio(tmp_path):
            fake_client = FakeGoogleClient()
            app = _app(tmp_path, fake_client)

            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "The cat stopped, looked into the camera and laughed",
                    "narrationScript": "",
                    "aspectRatio": "16:9",
                    "seconds": 8,
                    "videoToExtend": {
                        "videoBytes": "RkFLRV9WSURFT19CWVRFUw==",
                        "mimeType": "video/mp4",
                    },
                },
            )

            assert response.status_code == 200
            call = fake_client.models.calls[-1]
            assert call["video"] == {
                "videoBytes": "RkFLRV9WSURFT19CWVRFUw==",
                "mimeType": "video/mp4",
            }
            assert call["config"] == {
                "numberOfVideos": 1,
                "resolution": "720p",
            }
            assert "[DIRECTOR_EXTENSION_REQUEST]" in call["prompt"]


        def test_google_normal_video_generation_keeps_aspect_ratio_config(tmp_path):
            fake_client = FakeGoogleClient()
            app = _app(tmp_path, fake_client)

            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "cat playing football",
                    "narrationScript": "",
                    "aspectRatio": "9:16",
                    "seconds": 8,
                },
            )

            assert response.status_code == 200
            call = fake_client.models.calls[-1]
            assert call["config"]["aspectRatio"] == "9:16"
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("updated tests/test_google_video_extension_ref.py")
