from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"
test_file = ROOT / "tests" / "test_google_video_extension_ref.py"

content = runtime_file.read_text(encoding="utf-8")
lines = content.splitlines()


# 1) Replace the Google video extension block by line scanning.
start = None
for i, line in enumerate(lines):
    if line.strip() == "if video_to_extend:":
        # Ensure this is inside _generate_google_video by checking nearby context.
        nearby = "\n".join(lines[max(0, i - 40):i + 10])
        if "def _generate_google_video(" in nearby or "_generate_google_video" in "\n".join(lines[max(0, i - 80):i]):
            start = i
            break

if start is None:
    raise SystemExit("Could not find Google if video_to_extend block.")

end = None
for j in range(start + 1, len(lines)):
    if lines[j].strip().startswith("elif clean_start:"):
        end = j
        break

if end is None:
    raise SystemExit("Could not find elif clean_start after Google video_to_extend block.")

replacement = [
    "    if video_to_extend:",
    "        google_video_input = _coerce_google_video_extension_input(video_to_extend)",
    "        if google_video_input is not None:",
    '            kwargs["video"] = google_video_input',
    '        kwargs["prompt"] = (',
    '            "[DIRECTOR_EXTENSION_REQUEST]\\n"',
    "            f\"{prompt}\\n\\n\"",
    '            "[EXTENSION]\\n"',
    '            "This is a continuation of the previous clip. Ensure identical visual subjects and motion continuity."',
    "        )",
]

lines = lines[:start] + replacement + lines[end:]
content = "\n".join(lines) + "\n"
print("patched Google video extension block")


# 2) Add coercion helper before _generate_openai_video.
if "def _coerce_google_video_extension_input(" not in content:
    marker = "\ndef _generate_openai_video("
    idx = content.find(marker)
    if idx < 0:
        raise SystemExit("Could not find _generate_openai_video insertion point.")

    helper = dedent(
        '''
        def _coerce_google_video_extension_input(video_to_extend: Any) -> Any:
            if not video_to_extend:
                return None

            if isinstance(video_to_extend, dict):
                raw_b64 = (
                    video_to_extend.get("videoBytes")
                    or video_to_extend.get("video_bytes")
                    or video_to_extend.get("bytes")
                    or video_to_extend.get("data")
                )
                if raw_b64:
                    return {
                        "videoBytes": _strip_data_url_prefix(str(raw_b64)),
                        "mimeType": str(video_to_extend.get("mimeType") or video_to_extend.get("mime_type") or "video/mp4"),
                    }

                uri = (
                    video_to_extend.get("uri")
                    or video_to_extend.get("url")
                    or video_to_extend.get("name")
                    or video_to_extend.get("id")
                    or video_to_extend.get("value")
                )
                if uri:
                    return {
                        "uri": str(uri),
                        "mimeType": str(video_to_extend.get("mimeType") or video_to_extend.get("mime_type") or "video/mp4"),
                    }

                return video_to_extend

            if isinstance(video_to_extend, str):
                raw = video_to_extend.strip()
                if not raw:
                    return None

                if raw.startswith("data:video/"):
                    mime = raw.split(";", 1)[0].replace("data:", "", 1)
                    return {
                        "videoBytes": _strip_data_url_prefix(raw),
                        "mimeType": mime or "video/mp4",
                    }

                return {
                    "uri": raw,
                    "mimeType": "video/mp4",
                }

            return video_to_extend


        '''
    ).lstrip()

    content = content[:idx] + "\n" + helper + content[idx:]
    print("added Google extension input coercion helper")
else:
    print("Google extension input coercion helper already exists")


# 3) Replace _json_safe_video_ref to preserve uri/name/id/mimeType for extension.
start = content.find("def _json_safe_video_ref(video: Any) -> Any:")
if start < 0:
    raise SystemExit("Could not find _json_safe_video_ref.")

next_def = content.find("\ndef ", start + 1)
if next_def < 0:
    next_def = len(content)

replacement = dedent(
    '''
    def _json_safe_video_ref(video: Any) -> Any:
        if isinstance(video, (str, int, float, bool)) or video is None:
            return video

        if isinstance(video, dict):
            safe = {}
            for key, value in video.items():
                if key in {"data", "videoBytes", "video_bytes", "bytes"}:
                    continue
                safe[str(key)] = _json_safe_video_ref(value)
            return safe

        uri = _get_value(video, "uri")
        name = _get_value(video, "name")
        video_id = _get_value(video, "id")
        mime_type = _get_value(video, "mimeType") or _get_value(video, "mime_type") or "video/mp4"

        if uri or name or video_id:
            safe: dict[str, Any] = {}
            if uri:
                safe["uri"] = str(uri)
            if name:
                safe["name"] = str(name)
            if video_id:
                safe["id"] = str(video_id)
            if mime_type:
                safe["mimeType"] = str(mime_type)
            return safe

        return ""
    '''
).lstrip()

content = content[:start] + replacement + content[next_def:]
runtime_file.write_text(content, encoding="utf-8")
print("patched _json_safe_video_ref")


# 4) Add focused tests.
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


        def test_google_video_result_returns_provider_ref_for_extension(tmp_path):
            fake_client = FakeGoogleClient()
            app = _app(tmp_path, fake_client)

            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "cat playing football",
                    "narrationScript": "A cat plays football.",
                    "aspectRatio": "16:9",
                    "seconds": 4,
                },
            )

            assert response.status_code == 200
            payload = response.get_json()
            assert payload["videoRef"]["uri"] == "google://generated-video-1"
            assert payload["videoRef"]["mimeType"] == "video/mp4"


        def test_google_video_extension_coerces_video_ref_into_google_video_input(tmp_path):
            fake_client = FakeGoogleClient()
            app = _app(tmp_path, fake_client)

            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "The cat stopped, looked into the camera and laughed",
                    "narrationScript": "",
                    "aspectRatio": "16:9",
                    "seconds": 4,
                    "videoToExtend": {
                        "uri": "google://generated-video-1",
                        "mimeType": "video/mp4",
                    },
                },
            )

            assert response.status_code == 200
            call = fake_client.models.calls[-1]
            assert call["video"] == {
                "uri": "google://generated-video-1",
                "mimeType": "video/mp4",
            }
            assert "[DIRECTOR_EXTENSION_REQUEST]" in call["prompt"]
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("created tests/test_google_video_extension_ref.py")
