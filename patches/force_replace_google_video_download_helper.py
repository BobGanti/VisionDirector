from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"

content = runtime_file.read_text(encoding="utf-8")

start = content.find("def _download_google_video_bytes_with_client(")
if start < 0:
    raise SystemExit("Could not find _download_google_video_bytes_with_client.")

end = content.find("def _download_openai_video_data_url(", start)
if end < 0:
    raise SystemExit("Could not find _download_openai_video_data_url after Google helper.")

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

            if download is not None:
                try:
                    result = download(file=candidate)
                except TypeError:
                    try:
                        result = download(candidate)
                    except Exception:
                        result = None
                except Exception:
                    result = None

                for value in (result, candidate):
                    data = _bytes_from_possible_response(value)
                    if data:
                        return data

                    data = _bytes_from_google_file_save(value)
                    if data:
                        return data

            for value in (candidate,):
                data = _bytes_from_possible_response(value)
                if data:
                    return data

                data = _bytes_from_google_file_save(value)
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

content = content[:start] + replacement + content[end:]

runtime_file.write_text(content, encoding="utf-8")

print("Force-replaced Google video download helper block.")
print("download helper count:", content.count("def _download_google_video_bytes_with_client("))
print("save helper count:", content.count("def _bytes_from_google_file_save("))
