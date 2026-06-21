from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"

if not runtime_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/ai_runtime.py")


def replace_function(text: str, name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"^def {re.escape(name)}\(.*?\n(?=def |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    new_text, count = pattern.subn(dedent(replacement).lstrip(), text, count=1)
    if count != 1:
        raise SystemExit(f"Could not replace function {name}.")
    return new_text


content = runtime_file.read_text(encoding="utf-8")

if "import tempfile" not in content:
    content = content.replace("import time\n", "import time\nimport tempfile\n", 1)
    print("added tempfile import")


content = replace_function(
    content,
    "_poll_google_video_operation",
    '''
    def _poll_google_video_operation(client: Any, operation: Any) -> Any:
        for _ in range(90):
            if bool(_get_value(operation, "done")):
                return operation

            operations = getattr(client, "operations", None)
            getter = None
            if operations is not None:
                getter = (
                    getattr(operations, "get", None)
                    or getattr(operations, "get_videos_operation", None)
                    or getattr(operations, "getVideosOperation", None)
                )

            if getter is None:
                return operation

            try:
                operation = getter(operation)
            except TypeError:
                operation = getter(operation=operation)

            if bool(_get_value(operation, "done")):
                return operation

            time.sleep(8)

        return operation
    ''',
)


content = replace_function(
    content,
    "_extract_google_video_object",
    '''
    def _extract_google_video_object(operation: Any) -> Any:
        containers = [
            _get_value(operation, "response"),
            _get_value(operation, "result"),
            operation,
        ]

        for container in containers:
            if not container:
                continue

            generated = (
                _get_value(container, "generatedVideos")
                or _get_value(container, "generated_videos")
                or _get_value(container, "generatedvideos")
                or []
            )

            if generated and isinstance(generated, (list, tuple)):
                first = generated[0]
                return _get_value(first, "video") or first

            direct_video = _get_value(container, "video")
            if direct_video:
                return direct_video

        return None
    ''',
)


content = replace_function(
    content,
    "_download_google_video_bytes_with_client",
    '''
    def _download_google_video_bytes_with_client(client: Any, video: Any) -> bytes | None:
        files = getattr(client, "files", None)
        download = getattr(files, "download", None) if files is not None else None

        if download is None:
            return _bytes_from_google_file_save(video)

        candidates = [
            video,
            _get_value(video, "name"),
            _get_value(video, "uri"),
        ]

        for candidate in candidates:
            if not candidate:
                continue

            try:
                result = download(file=candidate)
            except TypeError:
                try:
                    result = download(candidate)
                except Exception:
                    continue
            except Exception:
                continue

            data = _bytes_from_possible_response(result)
            if data:
                return data

            data = _bytes_from_possible_response(candidate)
            if data:
                return data

            data = _bytes_from_google_file_save(candidate)
            if data:
                return data

        return _bytes_from_google_file_save(video)


    def _bytes_from_google_file_save(file_obj: Any) -> bytes | None:
        save = getattr(file_obj, "save", None)
        if save is None or not callable(save):
            return None

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                temp_path = Path(tmp.name)

            result = save(str(temp_path))

            data = _bytes_from_possible_response(result)
            if data:
                return data

            if temp_path.exists():
                data = temp_path.read_bytes()
                if data:
                    return data
        except Exception:
            return None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass

        return None
    ''',
)

runtime_file.write_text(content, encoding="utf-8")


test_file = ROOT / "tests" / "test_google_video_sdk_shape.py"
test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        from pathlib import Path

        from flask import Flask

        from smx_visiondirector import init_visiondirector
        from smx_visiondirector.storage import build_sqlite_storage


        class FakeGoogleVideoFile:
            def __init__(self):
                self.downloaded = False

            def save(self, path):
                if not self.downloaded:
                    raise RuntimeError("file was not downloaded before save")
                Path(path).write_bytes(b"FAKE_GOOGLE_VIDEO_BYTES")


        class FakeGeneratedVideo:
            def __init__(self):
                self.video = FakeGoogleVideoFile()


        class FakeCompletedOperation:
            done = True

            def __init__(self):
                self.result = type(
                    "Result",
                    (),
                    {"generated_videos": [FakeGeneratedVideo()]},
                )()


        class FakePendingOperation:
            done = False


        class FakeGoogleModels:
            def __init__(self, pending=False):
                self.pending = pending

            def generate_videos(self, **kwargs):
                if self.pending:
                    return FakePendingOperation()
                return FakeCompletedOperation()


        class FakeGoogleOperations:
            def get(self, operation):
                return FakeCompletedOperation()


        class FakeGoogleFiles:
            def download(self, *, file):
                file.downloaded = True
                return None


        class FakeGoogleClient:
            def __init__(self, pending=False):
                self.models = FakeGoogleModels(pending=pending)
                self.operations = FakeGoogleOperations()
                self.files = FakeGoogleFiles()


        def _app(tmp_path, fake_client):
            db_path = (
                tmp_path
                / "plugins"
                / "visiondirector"
                / "data"
                / "smx_visiondirector_dev.db"
            )
            storage = build_sqlite_storage(db_path)
            storage.initialize()

            app = Flask(__name__)
            init_visiondirector(
                app,
                project_root=tmp_path,
                storage=storage,
                ai_profile={
                    "main": {
                        "provider": "google",
                        "model": "host-google-model",
                        "client": fake_client,
                    }
                },
            )
            return app


        def test_google_video_route_supports_operation_result_generated_videos_and_file_download(tmp_path):
            app = _app(tmp_path, FakeGoogleClient())
            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "cat on motorbike",
                    "narrationScript": "A cat rides.",
                    "aspectRatio": "16:9",
                    "seconds": 4,
                },
            )

            assert response.status_code == 200
            payload = response.get_json()
            assert payload["url"].startswith("data:video/mp4;base64,")
            assert payload["jobId"]

            job_response = app.test_client().get(
                f"/visiondirector/api/render-jobs/{payload['jobId']}"
            )
            assert job_response.status_code == 200
            assert job_response.get_json()["job"]["status"] == "success"


        def test_google_video_route_supports_operations_get_positional_polling(tmp_path):
            app = _app(tmp_path, FakeGoogleClient(pending=True))
            response = app.test_client().post(
                "/visiondirector/api/ai/generate-video",
                json={
                    "supplier": "google",
                    "visualPrompt": "cat on motorbike",
                    "narrationScript": "A cat rides.",
                    "aspectRatio": "16:9",
                    "seconds": 4,
                },
            )

            assert response.status_code == 200
            assert response.get_json()["url"].startswith("data:video/mp4;base64,")
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("Patch complete: Google video SDK result/download shape is supported.")
