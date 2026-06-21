from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

start = content.find('    @bp.get("/<path:filename>")\n')
if start < 0:
    raise SystemExit('Could not find @bp.get("/<path:filename>") static route.')

end = content.find("\n    return bp", start)
if end < 0:
    raise SystemExit("Could not find return bp after static route.")

new_route = dedent(
    '''
        @bp.get("/<path:filename>")
        def static_file(filename: str):
            if filename in {"index.js", "index.css", "index.html"}:
                candidates = [
                    resolved_project_root / filename,
                    PROJECT_ROOT / filename,
                    Path.cwd() / filename,
                ]

                selected = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.exists() and candidate.is_file()
                    ),
                    None,
                )

                if selected is None:
                    return Response(
                        f"VisionDirector {filename} not found.",
                        status=500,
                        mimetype="text/plain",
                    )

                if filename == "index.js":
                    js = selected.read_text(encoding="utf-8")
                    js = _rewrite_runtime_js_urls(js)
                    return Response(js, mimetype="application/javascript")

                if filename == "index.css":
                    return Response(
                        selected.read_text(encoding="utf-8"),
                        mimetype="text/css",
                    )

                html = selected.read_text(encoding="utf-8")
                html = _inject_safe_runtime(
                    html,
                    config=resolved_config,
                    profile_registry=profile_registry,
                )
                html = _rewrite_index_asset_urls(html)
                return Response(html, mimetype="text/html")

            return send_from_directory(resolved_project_root, filename)

    '''
)

content = content[:start] + new_route + content[end:].lstrip("\n")
init_file.write_text(content, encoding="utf-8")
print("Repaired VisionDirector static route with package/project fallback for index assets.")
