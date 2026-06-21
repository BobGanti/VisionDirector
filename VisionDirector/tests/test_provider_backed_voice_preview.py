from __future__ import annotations

import base64

from flask import Flask

from smx_visiondirector import setup_visiondirector


class FakeGoogleModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        audio_b64 = base64.b64encode(b"google voice audio").decode("ascii")
        inline = type("Inline", (), {"data": audio_b64, "mime_type": "audio/wav"})()
        part = type("Part", (), {"inline_data": inline})()
        content = type("Content", (), {"parts": [part]})()
        candidate = type("Candidate", (), {"content": content})()
        return type("GoogleTTSResponse", (), {"candidates": [candidate]})()


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


class FakeOpenAISpeech:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return b"openai voice audio"


class FakeOpenAIAudio:
    def __init__(self):
        self.speech = FakeOpenAISpeech()


class FakeOpenAIClient:
    def __init__(self):
        self.audio = FakeOpenAIAudio()


def test_runtime_voice_preview_uses_provider_backend_not_browser_only(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {"provider": "google", "model": "google-main", "client": FakeGoogleClient()},
            "assistant": {"provider": "openai", "model": "openai-main", "client": FakeOpenAIClient()},
        },
    )

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    js = response.get_data(as_text=True)
    assert "__smxVisionDirectorProviderVoicePreview" in js
    assert "/visiondirector/api/ai/preview-voice" in js
    assert "new Audio(audioUrl)" in js
    assert "googleProvider.playVoicePreview" in js
    assert "openaiProvider.playVoicePreview" in js


def test_google_voice_preview_route_returns_provider_audio_and_uses_selected_voice(tmp_path):
    fake = FakeGoogleClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={"main": {"provider": "google", "model": "google-main", "client": fake}},
    )

    response = app.test_client().post(
        "/visiondirector/api/ai/preview-voice",
        json={
            "supplier": "google",
            "voice": "Puck",
            "speed": "natural",
            "traits": "warm delivery",
            "text": "Puck",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["audioUrl"].startswith("data:audio/wav;base64,")
    assert fake.models.calls
    assert fake.models.calls[-1]["model"]
    assert "Puck" in str(fake.models.calls[-1]["config"])


def test_openai_voice_preview_route_returns_provider_audio_and_uses_selected_voice(tmp_path):
    fake = FakeOpenAIClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={"main": {"provider": "openai", "model": "openai-main", "client": fake}},
    )

    response = app.test_client().post(
        "/visiondirector/api/ai/preview-voice",
        json={
            "supplier": "openai",
            "voice": "nova",
            "speed": "fast",
            "traits": "bright delivery",
            "text": "nova",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["audioUrl"].startswith("data:audio/wav;base64,")
    assert fake.audio.speech.calls
    call = fake.audio.speech.calls[-1]
    assert call["voice"] == "nova"
    assert call["input"] == "nova"
    assert call["response_format"] == "wav"



def test_provider_backed_voice_preview_is_final_play_voice_assignment(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {"provider": "google", "model": "google-main", "client": FakeGoogleClient()},
            "assistant": {"provider": "openai", "model": "openai-main", "client": FakeOpenAIClient()},
        },
    )

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    js = response.get_data(as_text=True)

    google_last = js.rfind("googleProvider.playVoicePreview")
    openai_last = js.rfind("openaiProvider.playVoicePreview")

    assert google_last > -1
    assert openai_last > -1

    google_tail = js[google_last : google_last + 300]
    openai_tail = js[openai_last : openai_last + 300]

    assert "__smxVisionDirectorProviderVoicePreview" in google_tail
    assert "__smxVisionDirectorProviderVoicePreview" in openai_tail
    assert "__smxVisionDirectorPlayVoicePreview" not in google_tail
    assert "__smxVisionDirectorPlayVoicePreview" not in openai_tail



def test_google_voice_preview_does_not_use_text_only_host_model(tmp_path):
    fake = FakeGoogleClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-2.5-flash",
                "client": fake,
            }
        },
    )

    response = app.test_client().post(
        "/visiondirector/api/ai/preview-voice",
        json={
            "supplier": "google",
            "voice": "Puck",
            "speed": "natural",
            "traits": "warm delivery",
            "text": "Puck",
        },
    )

    assert response.status_code == 200
    assert fake.models.calls
    assert fake.models.calls[-1]["model"] == "gemini-3.1-flash-tts-preview"
    assert response.get_json()["model"] == "gemini-3.1-flash-tts-preview"
