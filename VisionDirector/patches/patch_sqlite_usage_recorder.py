from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
usage_file = ROOT / "src" / "smx_visiondirector" / "usage.py"
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"

if not usage_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/usage.py")
if not init_file.exists():
    raise SystemExit("Missing src/smx_visiondirector/__init__.py")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


usage = usage_file.read_text(encoding="utf-8")

if "import sqlite3" not in usage:
    usage = usage.replace("import json\n", "import json\nimport sqlite3\n", 1)
    print("added sqlite3 import")

if "class SQLiteUsageRecorder" not in usage:
    marker = "\n\ndef new_usage_event(\n"
    if marker not in usage:
        raise SystemExit("Could not find new_usage_event marker in usage.py.")

    sqlite_recorder = dedent(
        r'''

        class SQLiteUsageRecorder(UsageRecorder):
            """Usage recorder backed by visiondirector_usage_events.

            This is plugin-owned operational telemetry only:
            token breakdowns, provider/model names, operation names, statuses,
            and latency. It does not store prompts, responses, API keys, or costs.
            """

            def __init__(self, storage: Any) -> None:
                self.storage = storage
                self._lock = Lock()
                self.storage.initialize()

            def _sqlite_path(self) -> Path:
                config = getattr(self.storage, "config", None)
                backend = getattr(config, "backend", "")
                sqlite_path = getattr(config, "sqlite_path", None)

                if backend != "sqlite" or sqlite_path is None:
                    raise NotImplementedError(
                        "SQLiteUsageRecorder currently requires SQLite storage. "
                        "PostgreSQL support will be wired through the production adapter later."
                    )

                return Path(sqlite_path)

            def record(self, event: UsageEvent) -> None:
                sqlite_path = self._sqlite_path()
                sqlite_path.parent.mkdir(parents=True, exist_ok=True)
                self.storage.initialize()

                metadata_json = json.dumps(
                    {
                        "finished_at": event.finished_at,
                    },
                    sort_keys=True,
                )

                with self._lock:
                    with sqlite3.connect(sqlite_path) as conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO visiondirector_usage_events "
                            "(id, timestamp, operation, provider, model, role, status, "
                            "input_tokens, output_tokens, total_tokens, cached_tokens, "
                            "reasoning_tokens, latency_ms, metadata_json) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                event.event_id,
                                event.started_at,
                                event.operation,
                                event.provider,
                                event.model,
                                event.role,
                                event.status,
                                event.input_tokens,
                                event.output_tokens,
                                event.total_tokens,
                                event.cached_tokens,
                                event.reasoning_tokens,
                                event.duration_ms,
                                metadata_json,
                            ),
                        )
                        conn.commit()

            def events(self) -> list[UsageEvent]:
                sqlite_path = self._sqlite_path()
                if not sqlite_path.exists():
                    return []

                with self._lock:
                    with sqlite3.connect(sqlite_path) as conn:
                        rows = conn.execute(
                            "SELECT id, timestamp, operation, provider, model, role, status, "
                            "input_tokens, output_tokens, total_tokens, cached_tokens, "
                            "reasoning_tokens, latency_ms, metadata_json "
                            "FROM visiondirector_usage_events "
                            "ORDER BY timestamp ASC, id ASC"
                        ).fetchall()

                events: list[UsageEvent] = []
                for row in rows:
                    metadata = {}
                    try:
                        metadata = json.loads(row[13] or "{}")
                    except json.JSONDecodeError:
                        metadata = {}

                    events.append(
                        UsageEvent(
                            event_id=str(row[0]),
                            started_at=str(row[1]),
                            finished_at=str(metadata.get("finished_at") or row[1]),
                            operation=str(row[2]),
                            provider=str(row[3]),
                            model=row[4],
                            role=row[5],
                            status=str(row[6]),
                            input_tokens=int(row[7] or 0),
                            output_tokens=int(row[8] or 0),
                            total_tokens=int(row[9] or 0),
                            cached_tokens=int(row[10] or 0),
                            reasoning_tokens=int(row[11] or 0),
                            duration_ms=int(row[12] or 0),
                        )
                    )

                return events
        '''
    )

    usage = usage.replace(marker, sqlite_recorder + marker, 1)
    print("added SQLiteUsageRecorder")
else:
    print("SQLiteUsageRecorder already present")

usage_file.write_text(usage, encoding="utf-8")


content = init_file.read_text(encoding="utf-8")

if "SQLiteUsageRecorder" not in content:
    if "JsonlUsageRecorder," in content:
        content = content.replace(
            "JsonlUsageRecorder,",
            "JsonlUsageRecorder,\n    SQLiteUsageRecorder,",
            1,
        )
    else:
        content = content.replace(
            "JsonlUsageRecorder",
            "JsonlUsageRecorder, SQLiteUsageRecorder",
            1,
        )
    print("added SQLiteUsageRecorder import")

old = '    usage_recorder = JsonlUsageRecorder(scaffold.data_dir / "usage_events.jsonl")'
new = '    usage_recorder = SQLiteUsageRecorder(storage)'

if old in content:
    content = content.replace(old, new, 1)
    print("setup_visiondirector now uses SQLiteUsageRecorder")
elif "usage_recorder = SQLiteUsageRecorder(storage)" in content:
    print("setup_visiondirector already uses SQLiteUsageRecorder")
else:
    raise SystemExit("Could not find setup_visiondirector usage recorder assignment.")

init_file.write_text(content, encoding="utf-8")


write_file(
    "tests/test_sqlite_usage_recorder.py",
    """
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
        text = '{\"visuals\":\"A cat riding a motorbike\",\"narration\":\"The cat rides.\"}'
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
    """,
)

print("Patch complete: usage events now use SQLite storage.")
