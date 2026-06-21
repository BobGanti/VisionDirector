from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"

content = runtime_file.read_text(encoding="utf-8")

pattern = re.compile(
    r"^def _download_google_video_bytes_with_client\(.*?\n(?=def _download_openai_video_data_url)",
    re.MULTILINE | re.DOTALL,
)

replacement = dedent(
    '''
    def _download_google_video_bytes_with_client(client: Any, video: Any) -> bytes | None:
        files = getattr(client, "files", None)
        download = getattr(files, "download", None) if files is not None else None

        candidates = [
            video,
            _get_value(video, "name"),
            _get_value(video, "uri"),
        ]

        for candidate in candidates:
            if not candidate:
                continue

            # Some Google SDK objects already know how to save themselves.
            data = _bytes_from_google_file_save(candidate)
            if data:
                return data

            if download is None:
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

            # client.files.download(...) may return bytes/stream/content directly.
            data = _bytes_from_possible_response(result)
            if data:
                return data

            # Google SDK examples download first, then call generated_video.video.save(path).
            data = _bytes_from_google_file_save(candidate)
            if data:
                return data

            # Some SDKs may return a file-like object that then supports save(...).
            data = _bytes_from_google_file_save(result)
            if data:
                return data

        return None


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


    '''
).lstrip()

content, count = pattern.subn(replacement, content, count=1)

if count != 1:
    raise SystemExit("Could not replace Google video download helper block.")

runtime_file.write_text(content, encoding="utf-8")
print("Patched Google video download helper to save after client.files.download.")
