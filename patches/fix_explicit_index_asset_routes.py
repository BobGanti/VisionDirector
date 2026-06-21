from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

if 'def visiondirector_index_js_asset():' in content:
    print("Explicit index asset routes already present.")
else:
    anchor = "    app.register_blueprint(bp, url_prefix=url_prefix)\n"
    idx = content.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find app.register_blueprint anchor.")

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
    )

    content = content[:idx] + route_block + content[idx:]
    init_file.write_text(content, encoding="utf-8")
    print("Inserted explicit VisionDirector index asset routes before blueprint registration.")

