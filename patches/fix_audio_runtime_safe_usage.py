from __future__ import annotations

from pathlib import Path
from textwrap import dedent

runtime_file = Path("src/smx_visiondirector/ai_runtime.py")
content = runtime_file.read_text(encoding="utf-8")

marker = "# smx-visiondirector audio runtime method bindings"
idx = content.find(marker)
if idx < 0:
    raise SystemExit("Could not find audio runtime method bindings block.")

helper_name = "def _smx_record_usage_if_available("
if helper_name not in content:
    insert_at = idx + len(marker)
    helper = dedent(
        '''


        def _smx_record_usage_if_available(runtime: Any, **kwargs: Any) -> None:
            record_usage = getattr(runtime, "_record_usage", None)
            if callable(record_usage):
                record_usage(**kwargs)
                return

            # Some migration states do not expose _record_usage as a method.
            # In that case, do not fail the user-facing audio request.
            return
        '''
    )

    content = content[:insert_at] + helper + content[insert_at:]
    print("added safe audio usage recorder helper")
else:
    print("safe audio usage recorder helper already present")

content = content.replace(
    "                self._record_usage(\n"
    "                    operation=operation,\n"
    "                    role=profile.role or clean_provider,\n"
    "                    provider=profile.provider,\n"
    "                    model=selected_model,\n"
    "                    status=status,\n"
    "                    started_at=started_at,\n"
    "                    tokens=tokens,\n"
    "                )",
    "                _smx_record_usage_if_available(\n"
    "                    self,\n"
    "                    operation=operation,\n"
    "                    role=profile.role or clean_provider,\n"
    "                    provider=profile.provider,\n"
    "                    model=selected_model,\n"
    "                    status=status,\n"
    "                    started_at=started_at,\n"
    "                    tokens=tokens,\n"
    "                )",
)

runtime_file.write_text(content, encoding="utf-8")
print("patched audio method bindings to use safe usage recording")
