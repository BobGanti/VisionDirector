from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


def test_runtime_patch_overrides_voice_preview_without_browser_provider_keys(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "host-google-model",
                "client": object(),
            },
            "assistant": {
                "provider": "openai",
                "model": "host-openai-model",
                "client": object(),
            },
        },
    )

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    js = response.get_data(as_text=True)

    assert "__smxVisionDirectorPlayVoicePreview" in js
    assert "googleProvider.playVoicePreview" in js
    assert "openaiProvider.playVoicePreview" in js
    assert "speechSynthesis" in js
    assert "BROWSER_TTS_UNAVAILABLE" in js
    assert "HOST_PROVIDER_NOT_READY" in js
