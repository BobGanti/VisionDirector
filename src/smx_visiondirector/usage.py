from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class TokenBreakdown:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class UsageEvent:
    event_id: str
    operation: str
    provider: str
    model: str | None
    role: str | None
    status: str
    started_at: str
    finished_at: str
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0


class UsageRecorder:
    def record(self, event: UsageEvent) -> None:
        raise NotImplementedError

    def events(self) -> list[UsageEvent]:
        raise NotImplementedError

    def report(self) -> dict[str, Any]:
        return build_usage_report(self.events())


class InMemoryUsageRecorder(UsageRecorder):
    def __init__(self) -> None:
        self._events: list[UsageEvent] = []
        self._lock = Lock()

    def record(self, event: UsageEvent) -> None:
        with self._lock:
            self._events.append(event)

    def events(self) -> list[UsageEvent]:
        with self._lock:
            return list(self._events)


class JsonlUsageRecorder(UsageRecorder):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, event: UsageEvent) -> None:
        payload = json.dumps(asdict(event), sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")

    def events(self) -> list[UsageEvent]:
        if not self.path.exists():
            return []

        events: list[UsageEvent] = []
        with self._lock:
            for raw_line in self.path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    events.append(UsageEvent(**payload))
                except TypeError:
                    continue
        return events


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


def new_usage_event(
    *,
    operation: str,
    provider: str,
    model: str | None,
    role: str | None,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    tokens: TokenBreakdown | None = None,
) -> UsageEvent:
    token_breakdown = tokens or TokenBreakdown()
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)

    return UsageEvent(
        event_id=uuid4().hex,
        operation=str(operation or "unknown"),
        provider=str(provider or "unknown"),
        model=model,
        role=role,
        status=str(status or "unknown"),
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_ms=max(duration_ms, 0),
        input_tokens=token_breakdown.input_tokens,
        output_tokens=token_breakdown.output_tokens,
        total_tokens=token_breakdown.total_tokens,
        cached_tokens=token_breakdown.cached_tokens,
        reasoning_tokens=token_breakdown.reasoning_tokens,
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def extract_token_breakdown(response: Any) -> TokenBreakdown:
    usage = (
        _get_value(response, "usage")
        or _get_value(response, "usage_metadata")
        or _get_value(response, "usageMetadata")
        or {}
    )

    input_tokens = _first_int(
        usage,
        "input_tokens",
        "prompt_tokens",
        "promptTokenCount",
        "inputTokenCount",
    )
    output_tokens = _first_int(
        usage,
        "output_tokens",
        "completion_tokens",
        "candidatesTokenCount",
        "outputTokenCount",
    )
    total_tokens = _first_int(
        usage,
        "total_tokens",
        "totalTokenCount",
    )
    cached_tokens = _first_int(
        usage,
        "cached_tokens",
        "cachedContentTokenCount",
    )
    reasoning_tokens = _first_int(
        usage,
        "reasoning_tokens",
        "thoughtsTokenCount",
    )

    input_details = _get_value(usage, "input_tokens_details") or {}
    output_details = _get_value(usage, "output_tokens_details") or {}

    cached_tokens = cached_tokens or _first_int(input_details, "cached_tokens")
    reasoning_tokens = reasoning_tokens or _first_int(output_details, "reasoning_tokens")

    if not total_tokens:
        total_tokens = input_tokens + output_tokens

    return TokenBreakdown(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
    )


def build_usage_report(events: list[UsageEvent]) -> dict[str, Any]:
    report = {
        "total_calls": len(events),
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_cached_tokens": 0,
        "total_reasoning_tokens": 0,
        "by_provider": {},
        "by_model": {},
        "by_operation": {},
        "events": [],
    }

    for event in events:
        _add_to_bucket(report, event)
        _add_to_group(report["by_provider"], event.provider, event)
        _add_to_group(report["by_model"], event.model or "unknown", event)
        _add_to_group(report["by_operation"], event.operation, event)

        report["events"].append(asdict(event))

    return report


def _add_to_bucket(bucket: dict[str, Any], event: UsageEvent) -> None:
    bucket["total_input_tokens"] += event.input_tokens
    bucket["total_output_tokens"] += event.output_tokens
    bucket["total_tokens"] += event.total_tokens
    bucket["total_cached_tokens"] += event.cached_tokens
    bucket["total_reasoning_tokens"] += event.reasoning_tokens


def _add_to_group(groups: dict[str, Any], key: str, event: UsageEvent) -> None:
    if key not in groups:
        groups[key] = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "success": 0,
            "error": 0,
        }

    group = groups[key]
    group["calls"] += 1
    group["input_tokens"] += event.input_tokens
    group["output_tokens"] += event.output_tokens
    group["total_tokens"] += event.total_tokens
    group["cached_tokens"] += event.cached_tokens
    group["reasoning_tokens"] += event.reasoning_tokens

    if event.status == "success":
        group["success"] += 1
    else:
        group["error"] += 1


def _first_int(obj: Any, *keys: str) -> int:
    for key in keys:
        value = _get_value(obj, key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, float):
            return max(int(value), 0)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return 0


def _get_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
