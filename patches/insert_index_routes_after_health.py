from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

if 'def visiondirector_index_js_asset():' in content:
    print("Explicit index asset routes already present.")
else:
    lines = content.splitlines()

    health_start = None
    for i, line in enumerate(lines):
        if line.strip() == '@bp.get("/health")':
            health_start = i
            break

    if health_start is None:
        raise SystemExit('Could not find @bp.get("/health") anchor.')

    insert_at = None
    for j in range(health_start + 1, len(lines)):
        if j > health_start + 1 and lines[j].startswith("    @bp."):
            insert_at = j
            break

    if insert_at is None:
        raise SystemExit("Could not find next blueprint route after health route.")

    route_block = dedent(
        '''
            def _visiondirector_index_asset_path(filename: str) -> Path | None:
                candidates = [
                    resolved_project_root / filename,
                    Path.cwd() / filename,
                    Path(__file__).resolve().parents[2] / filename,
                ]

                for candidate in candidates:
                    if candidate.exists() and candidate.is_file():
                        return candidate

                return None


            @bp.get("/index.js")
            def visiondirector_index_js_asset():
                selected = _visiondirector_index_asset_path("index.js")
                if selected is None:
                    return Response(
                        "VisionDirector index.js not found.",
                        status=500,
                        mimetype="text/plain",
                    )

                js = selected.read_text(encoding="utf-8")
                js = _rewrite_runtime_js_urls(js)
                return Response(js, mimetype="application/javascript")


            @bp.get("/index.css")
            def visiondirector_index_css_asset():
                selected = _visiondirector_index_asset_path("index.css")
                if selected is None:
                    return Response(
                        "VisionDirector index.css not found.",
                        status=500,
                        mimetype="text/plain",
                    )

                return Response(
                    selected.read_text(encoding="utf-8"),
                    mimetype="text/css",
                )


            @bp.get("/index.html")
            def visiondirector_index_html_asset():
                selected = _visiondirector_index_asset_path("index.html")
                if selected is None:
                    return Response(
                        "VisionDirector index.html not found.",
                        status=500,
                        mimetype="text/plain",
                    )

                html = selected.read_text(encoding="utf-8")
                html = _inject_safe_runtime(
                    html,
                    config=resolved_config,
                    profile_registry=profile_registry,
                )
                html = _rewrite_index_asset_urls(html)
                return Response(html, mimetype="text/html")


        '''
    ).splitlines()

    lines = lines[:insert_at] + route_block + lines[insert_at:]
    init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Inserted explicit /index.js, /index.css, and /index.html routes after /health.")

