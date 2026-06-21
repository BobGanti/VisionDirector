from __future__ import annotations

from pathlib import Path
from textwrap import dedent


ROOT = Path.cwd()

REQUIRED_ROOT_FILES = [
    "pyproject.toml",
    "src/vision_director/__init__.py",
    "index.html",
    "index.js",
]

missing = [name for name in REQUIRED_ROOT_FILES if not (ROOT / name).exists()]
if missing:
    raise SystemExit(
        "This patch must be run from the VisionDirector project root. "
        f"Missing expected file(s): {', '.join(missing)}"
    )


def write_file(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {relative_path}")


write_file(
    "src/vision_director/plugin.py",
    """
    from __future__ import annotations

    from pathlib import Path
    from typing import Any

    from flask import Blueprint, Response, send_from_directory, url_for

    from . import PROJECT_ROOT


    DEFAULT_URL_PREFIX = "/vision-director"


    def create_vision_director_blueprint(
        *,
        project_root: str | Path | None = None,
        ai_profile: dict[str, Any] | None = None,
    ) -> Blueprint:
        \"\"\"Create the VisionDirector Flask blueprint.

        The host framework owns provider/client construction and passes ai_profile in.
        VisionDirector stores the profile reference for later internal orchestration,
        but this route layer never exposes secret values back to the browser.
        \"\"\"
        resolved_project_root = Path(project_root or PROJECT_ROOT).resolve()

        bp = Blueprint("vision_director", __name__)
        bp.project_root = resolved_project_root
        bp.ai_profile = ai_profile

        @bp.get("/health")
        def vision_director_health():
            profile = ai_profile or {}
            return {
                "status": "ok",
                "package": "vision-director",
                "has_ai_profile": bool(profile),
                "has_main_profile": "main" in profile,
                "has_assistant_profile": "assistant" in profile,
            }

        @bp.get("/")
        def vision_director_home():
            index_file = resolved_project_root / "index.html"
            if not index_file.exists():
                return Response("VisionDirector index.html not found.", status=500)

            html = index_file.read_text(encoding="utf-8")
            html = _rewrite_index_asset_urls(html)
            return Response(html, mimetype="text/html")

        @bp.get("/<path:filename>")
        def vision_director_asset(filename: str):
            return send_from_directory(resolved_project_root, filename)

        return bp


    def setup_vision_director(
        app,
        *,
        project_root: str | Path | None = None,
        ai_profile: dict[str, Any] | None = None,
        url_prefix: str = DEFAULT_URL_PREFIX,
    ):
        \"\"\"Register VisionDirector on a host Flask app under a namespaced route.\"\"\"
        app.register_blueprint(
            create_vision_director_blueprint(
                project_root=project_root,
                ai_profile=ai_profile,
            ),
            url_prefix=url_prefix,
        )
        return app


    def _rewrite_index_asset_urls(html: str) -> str:
        \"\"\"Keep VisionDirector assets under /vision-director instead of host root.\"\"\"
        css_url = url_for("vision_director.vision_director_asset", filename="index.css")
        js_url = url_for("vision_director.vision_director_asset", filename="index.js")

        return (
            html.replace('href="/index.css"', f'href="{css_url}"')
            .replace("href='/index.css'", f"href='{css_url}'")
            .replace('src="/index.js"', f'src="{js_url}"')
            .replace("src='/index.js'", f"src='{js_url}'")
        )
    """,
)

write_file(
    "src/vision_director/__init__.py",
    """
    from __future__ import annotations

    from pathlib import Path

    __version__ = "0.1.0"

    PACKAGE_ROOT = Path(__file__).resolve().parent
    PROJECT_ROOT = PACKAGE_ROOT.parents[1]

    from .plugin import (  # noqa: E402
        DEFAULT_URL_PREFIX,
        create_vision_director_blueprint,
        setup_vision_director,
    )

    __all__ = [
        "DEFAULT_URL_PREFIX",
        "PACKAGE_ROOT",
        "PROJECT_ROOT",
        "__version__",
        "create_vision_director_blueprint",
        "setup_vision_director",
    ]
    """,
)

write_file(
    "tests/test_vision_director_plugin_api.py",
    """
    from __future__ import annotations

    from flask import Flask

    import vision_director
    from vision_director import setup_vision_director


    def test_setup_vision_director_is_public_api():
        assert callable(setup_vision_director)
        assert vision_director.DEFAULT_URL_PREFIX == "/vision-director"


    def test_setup_vision_director_registers_namespaced_health_route():
        app = Flask(__name__)

        setup_vision_director(
            app,
            project_root=vision_director.PROJECT_ROOT,
            ai_profile={
                "main": {"provider": "google", "model": "fake-main"},
                "assistant": {"provider": "openai", "model": "fake-assistant"},
            },
        )

        response = app.test_client().get("/vision-director/health")

        assert response.status_code == 200
        assert response.get_json() == {
            "status": "ok",
            "package": "vision-director",
            "has_ai_profile": True,
            "has_main_profile": True,
            "has_assistant_profile": True,
        }


    def test_vision_director_home_serves_index_under_namespace():
        app = Flask(__name__)
        setup_vision_director(app, project_root=vision_director.PROJECT_ROOT)

        response = app.test_client().get("/vision-director/")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "VisionDirector Elite" in body
        assert 'href="/vision-director/index.css"' in body
        assert 'src="/vision-director/index.js"' in body


    def test_vision_director_static_asset_is_namespaced():
        app = Flask(__name__)
        setup_vision_director(app, project_root=vision_director.PROJECT_ROOT)

        response = app.test_client().get("/vision-director/index.js")

        assert response.status_code == 200
        assert "MISSING_API_KEY" in response.get_data(as_text=True)
    """,
)

print("\nStep 2 complete: VisionDirector now exposes a minimal SyntaxMatrix-style plugin setup API.")
