from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
target = ROOT / "src" / "smx_visiondirector" / "__init__.py"

content = target.read_text(encoding="utf-8")

old = '''                html = _inject_safe_runtime(
                    html,
                    config=resolved_config,
                    ai_profile=ai_profile,
                )
                html = _rewrite_index_asset_urls(html)
'''

new = '''                html = _inject_safe_runtime(
                    html,
                    config=resolved_config,
                    ai_profile=ai_profile,
                )
                html = _inject_safe_ai_profile_metadata(html, ai_profile=ai_profile)
                html = _rewrite_index_asset_urls(html)
'''

if old not in content:
    raise SystemExit("Could not find home() runtime injection block to patch.")

content = content.replace(old, new, 1)

marker = "        def _rewrite_runtime_js_urls(js: str) -> str:"
helper = r'''
        def _inject_safe_ai_profile_metadata(
            html: str,
            *,
            ai_profile: dict[str, Any] | None,
        ) -> str:
            profile_registry = build_ai_profile_registry(ai_profile)
            safe_payload = {
                "aiProfile": profile_registry.safe_summary(),
            }

            script = (
                "<script>"
                "window.__SMX_VISIONDIRECTOR_AI_PROFILE__ = "
                f"{json.dumps(safe_payload, sort_keys=True)};"
                "</script>"
            )

            return html.replace("</head>", f"  {script}\n</head>", 1)


'''

if helper.strip() not in content:
    if marker not in content:
        raise SystemExit("Could not find _rewrite_runtime_js_urls marker.")
    content = content.replace(marker, helper + marker, 1)

target.write_text(content, encoding="utf-8")
print("fixed browser-safe AI profile metadata injection")
