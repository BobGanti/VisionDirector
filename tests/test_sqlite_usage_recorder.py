from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Flask

from smx_visiondirector import setup_visiondirector
from smx_visiondirector.storage import build_sqlite_storage
from smx_visiondirector.usage import (
    SQLiteUsageRecorder,
    TokenBreakdown,
    new_usage_event,
)


class FakeGoogleResponse:
    text = '{"visuals":"A cat riding a motorbike","narration":"The cat rides."}'
    usage_metadata = {
        "promptTokenCount": 11,
        "candidatesTokenCount": 7,
        "totalTokenCount": 18,
        "cachedContentTokenCount": 2,
        "thoughtsTokenCount": 1,
    }


class FakeGoogleModels:
    def generate_content(self, **kwargs):
        return FakeGoogleResponse()


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


def _event():
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    finished = started + timedelta(milliseconds=123)
    return new_usage_event(
        operation="parse_script",
        provider="google",
        model="gemini-test",
        role="main",
        status="success",
        started_at=started,
        finished_at=finished,
        tokens=TokenBreakdown(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cached_tokens=1,
            reasoning_tokens=2,
        ),
    )


def test_sqlite_usage_recorder_persists_events_and_report(tmp_path):
    db_path = (
        tmp_path
        / "plugins"
        / "visiondirector"
        / "data"
        / "smx_visiondirector_dev.db"
    )
    storage = build_sqlite_storage(db_path)
    storage.initialize()

    recorder = SQLiteUsageRecorder(storage)
    recorder.record(_event())

    fresh = SQLiteUsageRecorder(build_sqlite_storage(db_path))
    events = fresh.events()
    report = fresh.report()

    assert len(events) == 1
    assert events[0].operation == "parse_script"
    assert events[0].provider == "google"
    assert events[0].input_tokens == 10
    assert events[0].cached_tokens == 1

    assert report["total_calls"] == 1
    assert report["total_tokens"] == 15
    assert report["total_cached_tokens"] == 1
    assert report["total_reasoning_tokens"] == 2


def test_setup_visiondirector_records_usage_events_to_sqlite(tmp_path):
    app = Flask(__name__)
    fake_client = FakeGoogleClient()

    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-test",
                "client": fake_client,
            }
        },
    )

    response = app.test_client().post(
        "/visiondirector/api/ai/parse-script",
        json={
            "supplier": "google",
            "prompt": "Generate a cat riding a motorbike.",
        },
    )

    assert response.status_code == 200

    db_path = (
        tmp_path
        / "plugins"
        / "visiondirector"
        / "data"
        / "smx_visiondirector_dev.db"
    )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT operation, provider, input_tokens, output_tokens, total_tokens "
            "FROM visiondirector_usage_events"
        ).fetchall()

    assert rows == [("parse_script", "google", 11, 7, 18)]


def test_usage_report_endpoint_reads_sqlite_usage_events(tmp_path):
    app = Flask(__name__)
    fake_client = FakeGoogleClient()

    setup_visiondirector(
        app,
        project_root=tmp_path,
        ai_profile={
            "main": {
                "provider": "google",
                "model": "gemini-test",
                "client": fake_client,
            }
        },
    )

    client = app.test_client()
    client.post(
        "/visiondirector/api/ai/parse-script",
        json={
            "supplier": "google",
            "prompt": "Generate a cat riding a motorbike.",
        },
    )

    report_response = client.get("/visiondirector/api/usage/report")

    assert report_response.status_code == 200
    report = report_response.get_json()
    assert report["total_calls"] == 1
    assert report["total_tokens"] == 18
    assert report["by_provider"]["google"]["calls"] == 1
