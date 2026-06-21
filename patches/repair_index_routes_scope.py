from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
lines = init_file.read_text(encoding="utf-8").splitlines()


# 1) Remove wrongly inserted module-scope index asset block.
wrong_start = None
for i, line in enumerate(lines):
    if line == "def _visiondirector_index_asset_path(filename: str) -> Path | None:":
        wrong_start = i
        break

if wrong_start is not None:
    wrong_end = None
    for j in range(wrong_start, len(lines)):
        if "return Response(html, mimetype=\"text/html\")" in lines[j]:
            wrong_end = j + 1
            break

    if wrong_end is None:
        raise SystemExit("Found wrong module-scope asset block but could not find its end.")

    while wrong_end < len(lines) and lines[wrong_end].strip() == "":
        wrong_end += 1

    del lines[wrong_start:wrong_end]
    print(f"Removed module-scope index asset route block lines {wrong_start + 1}-{wrong_end}.")
else:
    print("No module-scope index asset route block found.")


# 2) Insert correctly indented routes inside create_visiondirector_blueprint().
if any(line.strip() == "def visiondirector_index_js_asset():" and line.startswith("    ") for line in lines):
    print("Correctly scoped index asset routes already present.")
else:
    insert_at = None
    for i, line in enumerate(lines):
        if line == "    def _host_provider_status_payload():":
            insert_at = i
            break

    if insert_at is None:
        raise SystemExit("Could not find _host_provider_status_payload anchor inside blueprint factory.")

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

    indented_block = [("    " + line) if line.strip() else "" for line in route_block]
    lines = lines[:insert_at] + indented_block + [""] + lines[insert_at:]
    print("Inserted correctly scoped index asset routes inside blueprint factory.")

init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
