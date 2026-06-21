from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()
init_file = ROOT / "src" / "smx_visiondirector" / "__init__.py"
runtime_file = ROOT / "src" / "smx_visiondirector" / "ai_runtime.py"

if not init_file.exists() or not runtime_file.exists():
    raise SystemExit("Run from VisionDirector root. Missing smx_visiondirector files.")


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


write_file(
    "src/smx_visiondirector/usage.py",
    """
    from __future__ import annotations

    import json
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
                    fh.write(payload + "\\n")

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
    """,
)

write_file(
    "src/smx_visiondirector/ai_runtime.py",
    """
    from __future__ import annotations

    from dataclasses import dataclass
    from typing import Any

    from .ai_profiles import (
        AIProfileRegistry,
        ProviderProfile,
        VisionDirectorAIProfileError,
    )
    from .usage import (
        TokenBreakdown,
        UsageRecorder,
        extract_token_breakdown,
        new_usage_event,
        utc_now,
    )


    class VisionDirectorAIExecutionError(RuntimeError):
        \"\"\"Raised when a host-provided AI client cannot execute the request.\"\"\"


    @dataclass(frozen=True)
    class AITextResult:
        role: str
        provider: str
        model: str | None
        text: str
        tokens: TokenBreakdown


    @dataclass(frozen=True)
    class AIImageResult:
        role: str
        provider: str
        model: str | None
        image_data_url: str | None
        tokens: TokenBreakdown


    @dataclass(frozen=True)
    class _ProviderTextResponse:
        text: str
        tokens: TokenBreakdown


    @dataclass(frozen=True)
    class _ProviderImageResponse:
        image_data_url: str | None
        tokens: TokenBreakdown


    class VisionDirectorAIRuntime:
        \"\"\"Executes AI work using host-provided model clients only.\"\"\"

        def __init__(
            self,
            profile_registry: AIProfileRegistry,
            *,
            usage_recorder: UsageRecorder | None = None,
        ):
            self.profile_registry = profile_registry
            self.usage_recorder = usage_recorder

        def generate_text(
            self,
            *,
            prompt: str,
            role: str = "main",
            model: str | None = None,
            operation: str = "generate_text",
        ) -> AITextResult:
            profile = self.profile_registry.require_role(role)
            return self._generate_text_with_profile(
                profile=profile,
                prompt=prompt,
                role=role,
                model=model,
                operation=operation,
            )

        def generate_text_for_provider(
            self,
            *,
            prompt: str,
            provider: str,
            model: str | None = None,
            operation: str = "generate_text",
        ) -> AITextResult:
            clean_provider = str(provider or "").strip().lower()
            profile = self.profile_registry.require_provider(clean_provider)
            return self._generate_text_with_profile(
                profile=profile,
                prompt=prompt,
                role=profile.role or clean_provider,
                model=model,
                operation=operation,
            )

        def generate_image_for_provider(
            self,
            *,
            prompt: str,
            provider: str,
            aspect_ratio: str = "9:16",
            model: str | None = None,
            operation: str = "generate_image",
        ) -> AIImageResult:
            clean_provider = str(provider or "").strip().lower()
            profile = self.profile_registry.require_provider(clean_provider)

            clean_prompt = str(prompt or "").strip()
            selected_model = model or profile.model

            if not clean_prompt:
                return AIImageResult(
                    role=profile.role or clean_provider,
                    provider=profile.provider,
                    model=selected_model,
                    image_data_url=None,
                    tokens=TokenBreakdown(),
                )

            if not selected_model:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host AI profile for provider '{profile.provider}' has no model."
                )

            started_at = utc_now()
            status = "success"
            tokens = TokenBreakdown()

            try:
                if profile.provider == "google":
                    provider_result = _generate_google_image(
                        profile,
                        prompt=clean_prompt,
                        model=selected_model,
                        aspect_ratio=aspect_ratio,
                    )
                elif profile.provider == "openai":
                    provider_result = _generate_openai_image(
                        profile,
                        prompt=clean_prompt,
                        model=selected_model,
                        aspect_ratio=aspect_ratio,
                    )
                else:
                    raise VisionDirectorAIExecutionError(
                        f"Unsupported VisionDirector image provider: {profile.provider}"
                    )

                tokens = provider_result.tokens
                return AIImageResult(
                    role=profile.role or clean_provider,
                    provider=profile.provider,
                    model=selected_model,
                    image_data_url=provider_result.image_data_url,
                    tokens=tokens,
                )
            except Exception:
                status = "error"
                raise
            finally:
                self._record_usage(
                    operation=operation,
                    role=profile.role or clean_provider,
                    provider=profile.provider,
                    model=selected_model,
                    status=status,
                    started_at=started_at,
                    tokens=tokens,
                )

        def _generate_text_with_profile(
            self,
            *,
            profile: ProviderProfile,
            prompt: str,
            role: str,
            model: str | None = None,
            operation: str = "generate_text",
        ) -> AITextResult:
            clean_prompt = str(prompt or "").strip()
            if not clean_prompt:
                raise VisionDirectorAIExecutionError("prompt is required")

            selected_model = model or profile.model
            if not selected_model:
                raise VisionDirectorAIProfileError(
                    f"VisionDirector host AI profile for provider '{profile.provider}' has no model."
                )

            started_at = utc_now()
            status = "success"
            tokens = TokenBreakdown()

            try:
                if profile.provider == "google":
                    provider_result = _generate_google_text(
                        profile,
                        prompt=clean_prompt,
                        model=selected_model,
                    )
                elif profile.provider == "openai":
                    provider_result = _generate_openai_text(
                        profile,
                        prompt=clean_prompt,
                        model=selected_model,
                    )
                else:
                    raise VisionDirectorAIExecutionError(
                        f"Unsupported VisionDirector text provider: {profile.provider}"
                    )

                tokens = provider_result.tokens
                return AITextResult(
                    role=role,
                    provider=profile.provider,
                    model=selected_model,
                    text=provider_result.text,
                    tokens=tokens,
                )
            except Exception:
                status = "error"
                raise
            finally:
                self._record_usage(
                    operation=operation,
                    role=role,
                    provider=profile.provider,
                    model=selected_model,
                    status=status,
                    started_at=started_at,
                    tokens=tokens,
                )

        def _record_usage(
            self,
            *,
            operation: str,
            role: str | None,
            provider: str,
            model: str | None,
            status: str,
            started_at,
            tokens: TokenBreakdown,
        ) -> None:
            if self.usage_recorder is None:
                return

            self.usage_recorder.record(
                new_usage_event(
                    operation=operation,
                    provider=provider,
                    model=model,
                    role=role,
                    status=status,
                    started_at=started_at,
                    finished_at=utc_now(),
                    tokens=tokens,
                )
            )


    def build_ai_runtime(
        profile_registry: AIProfileRegistry,
        *,
        usage_recorder: UsageRecorder | None = None,
    ) -> VisionDirectorAIRuntime:
        return VisionDirectorAIRuntime(
            profile_registry,
            usage_recorder=usage_recorder,
        )


    def _generate_google_text(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
    ) -> _ProviderTextResponse:
        client = profile.client
        models = getattr(client, "models", None)

        if models is None or not hasattr(models, "generate_content"):
            raise VisionDirectorAIExecutionError(
                "Google host client must expose client.models.generate_content(...)."
            )

        response = models.generate_content(
            model=model,
            contents=prompt,
        )
        return _ProviderTextResponse(
            text=_extract_text(response),
            tokens=extract_token_breakdown(response),
        )


    def _generate_openai_text(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
    ) -> _ProviderTextResponse:
        client = profile.client
        responses = getattr(client, "responses", None)

        if responses is None or not hasattr(responses, "create"):
            raise VisionDirectorAIExecutionError(
                "OpenAI host client must expose client.responses.create(...)."
            )

        response = responses.create(
            model=model,
            input=prompt,
        )
        return _ProviderTextResponse(
            text=_extract_text(response),
            tokens=extract_token_breakdown(response),
        )


    def _generate_google_image(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
        aspect_ratio: str,
    ) -> _ProviderImageResponse:
        client = profile.client
        models = getattr(client, "models", None)

        if models is None or not hasattr(models, "generate_content"):
            raise VisionDirectorAIExecutionError(
                "Google host client must expose client.models.generate_content(...)."
            )

        response = models.generate_content(
            model=model,
            contents={
                "parts": [
                    {
                        "text": (
                            "High-fidelity cinematic production keyframe: "
                            f"{prompt}. Photo-realistic lighting."
                        )
                    }
                ]
            },
            config={"imageConfig": {"aspectRatio": aspect_ratio}},
        )

        b64 = _extract_inline_image_b64(response)
        return _ProviderImageResponse(
            image_data_url=f"data:image/png;base64,{b64}" if b64 else None,
            tokens=extract_token_breakdown(response),
        )


    def _generate_openai_image(
        profile: ProviderProfile,
        *,
        prompt: str,
        model: str,
        aspect_ratio: str,
    ) -> _ProviderImageResponse:
        client = profile.client
        images = getattr(client, "images", None)

        if images is None or not hasattr(images, "generate"):
            raise VisionDirectorAIExecutionError(
                "OpenAI host client must expose client.images.generate(...)."
            )

        response = images.generate(
            model=model,
            prompt=prompt,
            size=_aspect_ratio_to_openai_size(aspect_ratio),
            n=1,
            output_format="png",
            quality="auto",
            background="auto",
        )

        b64 = _extract_openai_image_b64(response)
        return _ProviderImageResponse(
            image_data_url=f"data:image/png;base64,{b64}" if b64 else None,
            tokens=extract_token_breakdown(response),
        )


    def _aspect_ratio_to_openai_size(aspect_ratio: str) -> str:
        if aspect_ratio == "16:9":
            return "1536x1024"
        if aspect_ratio == "9:16":
            return "1024x1536"
        return "1024x1024"


    def _extract_text(response: Any) -> str:
        direct = getattr(response, "text", None)
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        if isinstance(response, dict):
            for key in ("text", "output_text"):
                value = response.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        raise VisionDirectorAIExecutionError("AI response did not contain text output.")


    def _extract_inline_image_b64(response: Any) -> str | None:
        candidates = _get_value(response, "candidates") or []
        for candidate in candidates:
            content = _get_value(candidate, "content") or {}
            parts = _get_value(content, "parts") or []
            for part in parts:
                inline_data = _get_value(part, "inlineData") or _get_value(part, "inline_data")
                if inline_data:
                    data = _get_value(inline_data, "data")
                    if isinstance(data, str) and data.strip():
                        return data.strip()
        return None


    def _extract_openai_image_b64(response: Any) -> str | None:
        data_items = _get_value(response, "data") or []
        if not data_items:
            return None

        first = data_items[0]
        b64 = _get_value(first, "b64_json")
        if isinstance(b64, str) and b64.strip():
            return b64.strip()

        return None


    def _get_value(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)
    """,
)

content = init_file.read_text(encoding="utf-8")

content = content.replace(
    "from .ai_runtime import VisionDirectorAIExecutionError, build_ai_runtime\n",
    "from .ai_runtime import VisionDirectorAIExecutionError, build_ai_runtime\n"
    "from .usage import JsonlUsageRecorder, UsageRecorder\n",
)

content = content.replace(
    "    ai_profile: dict[str, Any] | None = None,\n) -> Blueprint:",
    "    ai_profile: dict[str, Any] | None = None,\n    usage_recorder: UsageRecorder | None = None,\n) -> Blueprint:",
    1,
)

content = content.replace(
    "    profile_registry = build_ai_profile_registry(ai_profile)\n",
    "    profile_registry = build_ai_profile_registry(ai_profile)\n"
    "    resolved_usage_recorder = usage_recorder or JsonlUsageRecorder(\n"
    "        resolved_project_root / \"plugins\" / \"visiondirector\" / \"data\" / \"usage_events.jsonl\"\n"
    "    )\n",
    1,
)

usage_route = '''
    @bp.get("/api/usage/report")
    def usage_report():
        return resolved_usage_recorder.report()


'''

if 'def usage_report():' not in content:
    marker = '    @bp.get("/assets/<path:filename>")\n'
    if marker not in content:
        raise SystemExit("Could not find assets route marker.")
    content = content.replace(marker, usage_route + marker, 1)

content = content.replace(
    "build_ai_runtime(profile_registry).generate_text_for_provider(",
    "build_ai_runtime(profile_registry, usage_recorder=resolved_usage_recorder).generate_text_for_provider(",
)
content = content.replace(
    "build_ai_runtime(profile_registry).generate_image_for_provider(",
    "build_ai_runtime(profile_registry, usage_recorder=resolved_usage_recorder).generate_image_for_provider(",
)
content = content.replace(
    "build_ai_runtime(profile_registry).generate_text(",
    "build_ai_runtime(profile_registry, usage_recorder=resolved_usage_recorder).generate_text(",
)

content = content.replace(
    "provider=supplier,\n                prompt=_script_parser_prompt(prompt),",
    "operation=\"parse_script\",\n                provider=supplier,\n                prompt=_script_parser_prompt(prompt),",
)
content = content.replace(
    "provider=supplier,\n                prompt=prompt,\n                aspect_ratio=aspect_ratio,",
    "operation=\"generate_image\",\n                provider=supplier,\n                prompt=prompt,\n                aspect_ratio=aspect_ratio,",
)
content = content.replace(
    "role=role,\n                prompt=prompt,",
    "operation=\"generate_text\",\n                role=role,\n                prompt=prompt,",
)

content = content.replace(
    "def init_visiondirector(\n"
    "    app,\n"
    "    *,\n"
    "    config: dict[str, Any] | None = None,\n"
    "    project_root: str | Path | None = None,\n"
    "    init_schema: bool = False,\n"
    "    ai_profile: dict[str, Any] | None = None,\n):",
    "def init_visiondirector(\n"
    "    app,\n"
    "    *,\n"
    "    config: dict[str, Any] | None = None,\n"
    "    project_root: str | Path | None = None,\n"
    "    init_schema: bool = False,\n"
    "    ai_profile: dict[str, Any] | None = None,\n"
    "    usage_recorder: UsageRecorder | None = None,\n):",
)

content = content.replace(
    "            ai_profile=ai_profile,\n"
    "        ),\n"
    "        url_prefix=DEFAULT_URL_PREFIX,\n"
    "    )\n"
    "    return app\n",
    "            ai_profile=ai_profile,\n"
    "            usage_recorder=usage_recorder,\n"
    "        ),\n"
    "        url_prefix=DEFAULT_URL_PREFIX,\n"
    "    )\n"
    "    return app\n",
    1,
)

content = content.replace(
    "    config = _config_from_env_file(scaffold.env_file)\n\n"
    "    return init_visiondirector(",
    "    config = _config_from_env_file(scaffold.env_file)\n"
    "    usage_recorder = JsonlUsageRecorder(scaffold.data_dir / \"usage_events.jsonl\")\n\n"
    "    return init_visiondirector(",
)

content = content.replace(
    "        ai_profile=ai_profile,\n"
    "    )\n",
    "        ai_profile=ai_profile,\n"
    "        usage_recorder=usage_recorder,\n"
    "    )\n",
    1,
)

content = content.replace(
    '    "SmxVisionDirectorScaffold",\n',
    '    "SmxVisionDirectorScaffold",\n    "UsageRecorder",\n',
)

init_file.write_text(content, encoding="utf-8")
print("updated smx_visiondirector token usage tracking and report endpoint")

write_file(
    "tests/test_usage_tracking.py",
    """
    from __future__ import annotations

    from flask import Flask

    from smx_visiondirector import setup_visiondirector
    from smx_visiondirector.usage import extract_token_breakdown


    class FakeGoogleModels:
        def __init__(self):
            self.calls = []

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)
            if "config" in kwargs:
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "inlineData": {
                                            "data": "GOOGLE_IMAGE_B64"
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 11,
                        "candidatesTokenCount": 3,
                        "totalTokenCount": 14,
                        "cachedContentTokenCount": 2,
                    },
                }

            return {
                "text": '{"visuals":"A city","narration":"Hello"}',
                "usageMetadata": {
                    "promptTokenCount": 7,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 12,
                    "cachedContentTokenCount": 1,
                },
            }


    class FakeGoogleClient:
        def __init__(self):
            self.models = FakeGoogleModels()


    class FakeOpenAIResponses:
        def create(self, *, model, input):
            return {
                "output_text": "openai result",
                "usage": {
                    "input_tokens": 13,
                    "output_tokens": 8,
                    "total_tokens": 21,
                    "input_tokens_details": {"cached_tokens": 4},
                    "output_tokens_details": {"reasoning_tokens": 2},
                },
            }


    class FakeOpenAIClient:
        def __init__(self):
            self.responses = FakeOpenAIResponses()


    def test_extract_token_breakdown_supports_google_and_openai_shapes():
        google = extract_token_breakdown(
            {
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 4,
                    "totalTokenCount": 14,
                    "cachedContentTokenCount": 3,
                }
            }
        )
        assert google.as_dict() == {
            "input_tokens": 10,
            "output_tokens": 4,
            "total_tokens": 14,
            "cached_tokens": 3,
            "reasoning_tokens": 0,
        }

        openai = extract_token_breakdown(
            {
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 6,
                    "total_tokens": 26,
                    "input_tokens_details": {"cached_tokens": 5},
                    "output_tokens_details": {"reasoning_tokens": 2},
                }
            }
        )
        assert openai.as_dict() == {
            "input_tokens": 20,
            "output_tokens": 6,
            "total_tokens": 26,
            "cached_tokens": 5,
            "reasoning_tokens": 2,
        }


    def test_usage_report_breaks_down_tokens_without_price_or_prompt_leak(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "SECRET_GOOGLE",
                    "client": FakeGoogleClient(),
                },
                "assistant": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "SECRET_OPENAI",
                    "client": FakeOpenAIClient(),
                },
            },
        )

        client = app.test_client()

        parse_response = client.post(
            "/visiondirector/api/ai/parse-script",
            json={
                "supplier": "google",
                "prompt": "CONFIDENTIAL_PROMPT_FOR_SCRIPT",
            },
        )
        assert parse_response.status_code == 200

        image_response = client.post(
            "/visiondirector/api/ai/generate-image",
            json={
                "supplier": "google",
                "prompt": "CONFIDENTIAL_PROMPT_FOR_IMAGE",
                "aspectRatio": "16:9",
            },
        )
        assert image_response.status_code == 200

        text_response = client.post(
            "/visiondirector/api/ai/generate-text",
            json={
                "role": "assistant",
                "prompt": "CONFIDENTIAL_PROMPT_FOR_TEXT",
            },
        )
        assert text_response.status_code == 200

        report_response = client.get("/visiondirector/api/usage/report")
        assert report_response.status_code == 200

        report = report_response.get_json()
        assert report["total_calls"] == 3
        assert report["total_input_tokens"] == 31
        assert report["total_output_tokens"] == 16
        assert report["total_tokens"] == 47
        assert report["total_cached_tokens"] == 7
        assert report["total_reasoning_tokens"] == 2

        assert report["by_provider"]["google"]["calls"] == 2
        assert report["by_provider"]["google"]["total_tokens"] == 26
        assert report["by_provider"]["openai"]["calls"] == 1
        assert report["by_provider"]["openai"]["total_tokens"] == 21

        assert report["by_operation"]["parse_script"]["total_tokens"] == 12
        assert report["by_operation"]["generate_image"]["total_tokens"] == 14
        assert report["by_operation"]["generate_text"]["total_tokens"] == 21

        body = report_response.get_data(as_text=True)
        assert "SECRET_GOOGLE" not in body
        assert "SECRET_OPENAI" not in body
        assert "CONFIDENTIAL_PROMPT_FOR_SCRIPT" not in body
        assert "CONFIDENTIAL_PROMPT_FOR_IMAGE" not in body
        assert "CONFIDENTIAL_PROMPT_FOR_TEXT" not in body
        assert "price" not in body.lower()
        assert "cost" not in body.lower()
        assert "currency" not in body.lower()
    """,
)

print("Patch complete: VisionDirector tracks token usage breakdown only, with no price/cost fields.")
