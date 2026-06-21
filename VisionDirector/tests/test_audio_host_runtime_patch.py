from __future__ import annotations

import base64

from flask import Flask

from smx_visiondirector import setup_visiondirector


AUDIO_DATA_URL = "data:audio/wav;base64," + base64.b64encode(b"fake-audio").decode("ascii")


class FakeGoogleModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return type("GoogleTextResponse", (), {"text": "fake google audio text"})()


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


class FakeOpenAITranscriptions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("OpenAITranscript", (), {"text": "fake openai transcript"})()


class FakeOpenAIAudio:
    def __init__(self):
        self.transcriptions = FakeOpenAITranscriptions()


class FakeOpenAIResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("OpenAIResponse", (), {"output_text": "fake openai voice traits"})()


class FakeOpenAIClient:
    def __init__(self):
        self.audio = FakeOpenAIAudio()
        self.responses = FakeOpenAIResponses()


def test_runtime_js_overrides_audio_methods_to_host_backend(tmp_path):
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
    assert "__smxVisionDirectorTranscribeAudio" in js
    assert "__smxVisionDirectorAnalyzeVoice" in js
    assert "googleProvider.analyzeVoice" in js
    assert "googleProvider.transcribeAudio" in js
    assert "openaiProvider.analyzeVoice" in js
    assert "openaiProvider.transcribeAudio" in js


def test_google_transcribe_audio_route_uses_host_client(tmp_path):
    fake = FakeGoogleClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={"main": {"provider": "google", "model": "google-main", "client": fake}},
    )

    response = app.test_client().post(
        "/visiondirector/api/ai/transcribe-audio",
        json={"supplier": "google", "audioBase64": AUDIO_DATA_URL},
    )

    assert response.status_code == 200
    assert response.get_json()["text"] == "fake google audio text"
    assert fake.models.calls
    assert fake.models.calls[-1]["model"]


def test_google_analyze_voice_route_uses_host_client(tmp_path):
    fake = FakeGoogleClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={"main": {"provider": "google", "model": "google-main", "client": fake}},
    )

    response = app.test_client().post(
        "/visiondirector/api/ai/analyze-voice",
        json={"supplier": "google", "audioBase64": AUDIO_DATA_URL, "sentiment": "joyful"},
    )

    assert response.status_code == 200
    assert response.get_json()["traits"] == "fake google audio text"
    assert fake.models.calls
    call_text = str(fake.models.calls[-1]["contents"])
    assert "VOCAL FORENSIC ANALYST" in call_text
    assert "joyful" in call_text


def test_openai_audio_routes_use_host_client(tmp_path):
    fake = FakeOpenAIClient()
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={"main": {"provider": "openai", "model": "openai-main", "client": fake}},
    )

    transcribe = app.test_client().post(
        "/visiondirector/api/ai/transcribe-audio",
        json={"supplier": "openai", "audioBase64": AUDIO_DATA_URL},
    )
    analyze = app.test_client().post(
        "/visiondirector/api/ai/analyze-voice",
        json={"supplier": "openai", "audioBase64": AUDIO_DATA_URL, "sentiment": "neutral"},
    )

    assert transcribe.status_code == 200
    assert transcribe.get_json()["text"] == "fake openai transcript"
    assert analyze.status_code == 200
    assert analyze.get_json()["traits"] == "fake openai voice traits"
    assert fake.audio.transcriptions.calls
    assert fake.responses.calls
