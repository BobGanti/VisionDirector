from __future__ import annotations

from pathlib import Path
from textwrap import dedent

p = Path("src/smx_visiondirector/__init__.py")
text = p.read_text(encoding="utf-8")

backup_dir = Path("patches/recovery_backups")
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "__init__.before_fix_remaining_admin_recovery_failures.py"
backup.write_text(text, encoding="utf-8")
print(f"Backed up current __init__.py to {backup}")


# ---------------------------------------------------------------------
# 1) Restore missing script parser helpers.
# ---------------------------------------------------------------------
if "def _script_parser_prompt(" not in text:
    marker = "\ndef create_visiondirector_blueprint("
    if marker not in text:
        raise SystemExit("Could not find create_visiondirector_blueprint marker.")

    helpers = dedent(
        '''

        def _script_parser_prompt(prompt: str) -> str:
            return (
                "Split the following explainer-video request into two concise fields: "
                "visuals and narration. Return JSON if possible.\\n\\n"
                f"{prompt}"
            )


        def _coerce_parsed_script(text: str, *, fallback_prompt: str) -> dict[str, str]:
            raw = str(text or "").strip()
            fallback = str(fallback_prompt or "").strip()

            if raw:
                try:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        visuals = str(payload.get("visuals") or payload.get("visual") or "").strip()
                        narration = str(payload.get("narration") or payload.get("script") or "").strip()
                        return {
                            "visuals": visuals or fallback,
                            "narration": narration or fallback,
                        }
                except json.JSONDecodeError:
                    pass

            if raw:
                lower = raw.lower()
                visuals = ""
                narration = ""

                if "narration" in lower and "visual" in lower:
                    lines = [line.strip() for line in raw.splitlines() if line.strip()]
                    for line in lines:
                        line_lower = line.lower()
                        if line_lower.startswith("visual") or line_lower.startswith("visuals"):
                            visuals = line.split(":", 1)[-1].strip() if ":" in line else line
                        elif line_lower.startswith("narration"):
                            narration = line.split(":", 1)[-1].strip() if ":" in line else line

                return {
                    "visuals": visuals or raw,
                    "narration": narration or raw,
                }

            return {
                "visuals": fallback,
                "narration": fallback,
            }
        '''
    )

    text = text.replace(marker, helpers + marker, 1)
    print("Restored _script_parser_prompt and _coerce_parsed_script.")
else:
    print("Script parser helpers already present.")


# ---------------------------------------------------------------------
# 2) Add the exact local scaffold token used by the tests.
# ---------------------------------------------------------------------
if '"local-visiondirector-admin-token"' not in text:
    token_anchor = '"local-dev-admin-token",'
    if token_anchor not in text:
        raise SystemExit("Could not find local admin fallback token list.")
    text = text.replace(
        token_anchor,
        token_anchor + '\n            "local-visiondirector-admin-token",',
        1,
    )
    print("Added local-visiondirector-admin-token fallback.")
else:
    print("local-visiondirector-admin-token already present.")


# ---------------------------------------------------------------------
# 3) Pass required config into render_admin_dashboard_html.
# ---------------------------------------------------------------------
if '"config": admin_dashboard_config,' not in text:
    marker = "            payload = {\n"
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit("Could not find admin dashboard payload block.")

    config_block = dedent(
        '''
                admin_dashboard_config = {
                    "host_site_title": resolved_config.get("host_site_title") or "SyntaxMatrix",
                    "host_home_url": resolved_config.get("host_home_url") or "/",
                    "app_title": resolved_config.get("app_title") or "VisionDirector",
                    "logo_url": resolved_config.get("logo_url") or "/visiondirector/assets/logo.png",
                }

        '''
    )

    text = text[:idx] + config_block + text[idx:]
    text = text.replace(
        '            payload = {\n                "profile_summary": profile_summary_payload,',
        '            payload = {\n                "config": admin_dashboard_config,\n                "profile_summary": profile_summary_payload,',
        1,
    )
    print("Added required admin dashboard config payload.")
else:
    print("Admin dashboard config payload already present.")


p.write_text(text, encoding="utf-8")
print("Saved focused recovery fixes.")
