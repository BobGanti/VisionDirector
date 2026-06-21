from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
test_file = Path("tests/test_provider_backed_voice_preview.py")

content = runtime_file.read_text(encoding="utf-8")

if "def _smx_audio_bytes_from_inline_data(" not in content:
    start = content.find("def _smx_extract_google_audio_data_url(response: Any) -> str:")
    if start < 0:
        raise SystemExit("Could not find _smx_extract_google_audio_data_url.")

    next_func = content.find("\ndef _smx_google_voice_preview(", start)
    if next_func < 0:
        raise SystemExit("Could not find _smx_google_voice_preview after extractor.")

    replacement = dedent(
        r'''
        def _smx_audio_bytes_from_inline_data(data: Any) -> bytes:
            if isinstance(data, bytes):
                return data
            if isinstance(data, bytearray):
                return bytes(data)

            if isinstance(data, str):
                raw = data.strip()
                if raw.startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                try:
                    return base64.b64decode(raw)
                except Exception as exc:
                    raise VisionDirectorAIExecutionError("TTS_PREVIEW_INVALID_AUDIO_BASE64") from exc

            raise VisionDirectorAIExecutionError("TTS_PREVIEW_UNSUPPORTED_AUDIO_DATA")


        def _smx_audio_sample_rate_from_mime(mime_type: str | None) -> int:
            text = str(mime_type or "").lower()
            for token in text.replace(";", " ").replace(",", " ").split():
                if token.startswith("rate="):
                    try:
                        return int(token.split("=", 1)[1])
                    except Exception:
                        pass
            return 24000


        def _smx_wav_bytes_from_pcm(
            pcm: bytes,
            *,
            sample_rate: int = 24000,
            channels: int = 1,
            sample_width: int = 2,
        ) -> bytes:
            if pcm.startswith(b"RIFF") and b"WAVE" in pcm[:16]:
                return pcm

            bits_per_sample = sample_width * 8
            byte_rate = sample_rate * channels * sample_width
            block_align = channels * sample_width
            data_size = len(pcm)
            riff_size = 36 + data_size

            header = b"".join(
                [
                    b"RIFF",
                    riff_size.to_bytes(4, "little"),
                    b"WAVE",
                    b"fmt ",
                    (16).to_bytes(4, "little"),
                    (1).to_bytes(2, "little"),
                    channels.to_bytes(2, "little"),
                    sample_rate.to_bytes(4, "little"),
                    byte_rate.to_bytes(4, "little"),
                    block_align.to_bytes(2, "little"),
                    bits_per_sample.to_bytes(2, "little"),
                    b"data",
                    data_size.to_bytes(4, "little"),
                ]
            )
            return header + pcm


        def _smx_extract_google_audio_data_url(response: Any) -> str:
            candidates = _get_value(response, "candidates") or []
            for candidate in candidates:
                content = _get_value(candidate, "content")
                parts = _get_value(content, "parts") or []
                for part in parts:
                    inline = (
                        _get_value(part, "inline_data")
                        or _get_value(part, "inlineData")
                    )
                    if not inline:
                        continue

                    data = _get_value(inline, "data")
                    if data is None:
                        continue

                    mime_type = (
                        _get_value(inline, "mime_type")
                        or _get_value(inline, "mimeType")
                        or "audio/pcm;rate=24000"
                    )

                    pcm_or_wav = _smx_audio_bytes_from_inline_data(data)
                    sample_rate = _smx_audio_sample_rate_from_mime(str(mime_type))
                    wav_bytes = _smx_wav_bytes_from_pcm(
                        pcm_or_wav,
                        sample_rate=sample_rate,
                        channels=1,
                        sample_width=2,
                    )
                    wav_b64 = base64.b64encode(wav_bytes).decode("ascii")
                    return f"data:audio/wav;base64,{wav_b64}"

            raise VisionDirectorAIExecutionError("TTS_PREVIEW_NO_AUDIO_RETURNED")
        '''
    ).lstrip()

    content = content[:start] + replacement + content[next_func:]
    runtime_file.write_text(content, encoding="utf-8")
    print("Patched Google TTS extraction to wrap PCM bytes as browser-playable WAV.")
else:
    print("Google TTS PCM-to-WAV wrapper already present.")


test_content = test_file.read_text(encoding="utf-8")

if "test_google_voice_preview_wraps_pcm_bytes_as_browser_playable_wav" not in test_content:
    test_content += dedent(
        r'''


        def test_google_voice_preview_wraps_pcm_bytes_as_browser_playable_wav(tmp_path):
            class BytesGoogleModels:
                def __init__(self):
                    self.calls = []

                def generate_content(self, **kwargs):
                    self.calls.append(kwargs)
                    inline = type(
                        "Inline",
                        (),
                        {
                            "data": b"\x00\x00\x01\x00\x02\x00\x03\x00",
                            "mime_type": "audio/pcm;rate=24000",
                        },
                    )()
                    part = type("Part", (), {"inline_data": inline})()
                    content = type("Content", (), {"parts": [part]})()
                    candidate = type("Candidate", (), {"content": content})()
                    return type("GoogleTTSResponse", (), {"candidates": [candidate]})()

            class BytesGoogleClient:
                def __init__(self):
                    self.models = BytesGoogleModels()

            fake = BytesGoogleClient()
            app = Flask(__name__)
            setup_visiondirector(
                app,
                project_root=tmp_path,
                ai_profile={"main": {"provider": "google", "model": "gemini-2.5-flash", "client": fake}},
            )

            response = app.test_client().post(
                "/visiondirector/api/ai/preview-voice",
                json={
                    "supplier": "google",
                    "voice": "Kore",
                    "speed": "natural",
                    "traits": "clear delivery",
                    "text": "Kore",
                },
            )

            assert response.status_code == 200
            audio_url = response.get_json()["audioUrl"]
            assert audio_url.startswith("data:audio/wav;base64,")

            payload = audio_url.split(",", 1)[1]
            wav_bytes = base64.b64decode(payload)
            assert wav_bytes[:4] == b"RIFF"
            assert wav_bytes[8:12] == b"WAVE"
        '''
    )

    test_file.write_text(test_content, encoding="utf-8")
    print("Added PCM-to-WAV regression test.")
else:
    print("PCM-to-WAV regression test already present.")
