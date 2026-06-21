from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
target = ROOT / "src" / "smx_visiondirector" / "__init__.py"

content = target.read_text(encoding="utf-8")

start = content.index("        def _inject_safe_runtime(")
end = content.index("        def _rewrite_runtime_js_urls", start)

replacement = r'''
        def _inject_safe_runtime(
            html: str,
            *,
            config: dict[str, Any],
            ai_profile: dict[str, Any] | None,
        ) -> str:
            profile_registry = build_ai_profile_registry(ai_profile)

            runtime = {
                "appTitle": config.get("app_title") or "VisionDirector",
                "hostSiteTitle": config.get("host_site_title") or "SyntaxMatrix",
                "hostHomeUrl": config.get("host_home_url") or "/",
                "appHomeUrl": config.get("app_home_url") or DEFAULT_URL_PREFIX,
                "hasAiProfile": profile_registry.has_any(),
                "hasMainProfile": profile_registry.has_role("main"),
                "hasAssistantProfile": profile_registry.has_role("assistant"),
                "aiProfile": profile_registry.safe_summary(),
            }

            script = (
                "<script>"
                "window.__SMX_VISIONDIRECTOR__ = "
                f"{json.dumps(runtime, sort_keys=True)};"
                "window.process = window.process || { env: {} };"
                "window.process.env = window.process.env || {};"
                "window.process.env.API_KEY = window.process.env.API_KEY || '';"
                "</script>"
            )

            return html.replace("<head>", f"<head>\n  {script}", 1)


'''

target.write_text(content[:start] + replacement + content[end:], encoding="utf-8")
print("fixed safe aiProfile browser runtime metadata")
