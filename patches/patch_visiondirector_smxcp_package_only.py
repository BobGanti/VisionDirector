from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()

required = ["pyproject.toml", "index.html", "index.js"]
missing = [name for name in required if not (ROOT / name).exists()]
if missing:
    raise SystemExit(
        "Run this patch from the VisionDirector project root. "
        f"Missing: {', '.join(missing)}"
    )


def write_file(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"wrote {rel}")


write_file(
    "pyproject.toml",
    """
    [build-system]
    requires = ["setuptools>=69", "wheel"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "smx-visiondirector"
    version = "0.1.0"
    description = "VisionDirector pluggable module for SyntaxMatrix host applications."
    readme = "README.md"
    requires-python = ">=3.10"
    dependencies = [
        "Flask>=3.0,<4",
    ]

    [project.optional-dependencies]
    test = [
        "pytest>=8,<9",
    ]

    [tool.setuptools]
    package-dir = {"" = "src"}

    [tool.setuptools.packages.find]
    where = ["src"]
    """,
)

write_file(
    "README.md",
    """
    # VisionDirector

    VisionDirector is a pluggable SyntaxMatrix module.

    Host usage:

    ```python
    from smx_visiondirector import setup_visiondirector

    setup_visiondirector(
        app=app,
        project_root=PROJECT_ROOT,
        init_schema=True,
        ai_profile=VISIONDIRECTOR_AGENTS_PROFILES,
    )
    ```

    The host builds AI provider clients and passes them through `ai_profile`.
    VisionDirector must not instantiate model/provider clients independently.
    """,
)

write_file(
    "src/smx_visiondirector/smxcp.py",
    r"""
    from __future__ import annotations

    from dataclasses import dataclass
    from pathlib import Path


    PLUGINS_DIR_NAME = "plugins"
    SCAFFOLD_DIR_NAME = "visiondirector"
    SETUP_FILE_NAME = "smx_visiondirector_setup.py"
    ENV_EXAMPLE_FILE_NAME = ".smx_visiondirector_example.env"
    ENV_FILE_NAME = ".smx_visiondirector.env"
    DEPLOY_ENV_EXAMPLE_FILE_NAME = ".smx_visiondirector.deploy_example.env"
    DATA_DIR_NAME = "data"
    ASSETS_DIR_NAME = "assets"

    FALLBACK_PNG_BYTES = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


    @dataclass(frozen=True)
    class SmxVisionDirectorScaffold:
        project_root: Path
        scaffold_dir: Path
        data_dir: Path
        assets_dir: Path
        setup_file: Path
        env_example_file: Path
        env_file: Path
        deploy_env_example_file: Path
        logo_file: Path
        favicon_file: Path


    def ensure_visiondirector_scaffold(
        *,
        project_root: str | Path | None = None,
    ) -> SmxVisionDirectorScaffold:
        root = Path(project_root or Path.cwd()).resolve()

        scaffold_dir = root / PLUGINS_DIR_NAME / SCAFFOLD_DIR_NAME
        data_dir = scaffold_dir / DATA_DIR_NAME
        assets_dir = scaffold_dir / ASSETS_DIR_NAME

        setup_file = scaffold_dir / SETUP_FILE_NAME
        env_example_file = scaffold_dir / ENV_EXAMPLE_FILE_NAME
        env_file = scaffold_dir / ENV_FILE_NAME
        deploy_env_example_file = scaffold_dir / DEPLOY_ENV_EXAMPLE_FILE_NAME
        logo_file = assets_dir / "logo.png"
        favicon_file = assets_dir / "favicon.png"

        scaffold_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)

        _write_if_missing(scaffold_dir / "__init__.py", "")
        _write_if_missing(setup_file, _render_setup_file())
        _write_if_missing(env_example_file, _render_env_example_file())
        _write_if_missing(env_file, _render_runtime_env_file(assets_dir=assets_dir))
        _write_if_missing(deploy_env_example_file, _render_deploy_env_example_file())
        _write_bytes_if_missing(logo_file, FALLBACK_PNG_BYTES)
        _write_bytes_if_missing(favicon_file, FALLBACK_PNG_BYTES)

        return SmxVisionDirectorScaffold(
            project_root=root,
            scaffold_dir=scaffold_dir,
            data_dir=data_dir,
            assets_dir=assets_dir,
            setup_file=setup_file,
            env_example_file=env_example_file,
            env_file=env_file,
            deploy_env_example_file=deploy_env_example_file,
            logo_file=logo_file,
            favicon_file=favicon_file,
        )


    def _write_if_missing(path: Path, content: str) -> None:
        if path.exists():
            return
        path.write_text(content, encoding="utf-8")


    def _write_bytes_if_missing(path: Path, content: bytes) -> None:
        if path.exists():
            return
        path.write_bytes(content)


    def _path_value(path: Path) -> str:
        return path.resolve().as_posix()


    def _render_setup_file() -> str:
        return '''from __future__ import annotations

from pathlib import Path
from smx_visiondirector import setup_visiondirector as _setup_visiondirector


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def setup_visiondirector(app, *, init_schema: bool = True, ai_profile=None):
    """
    Initialize VisionDirector for this client project.

    The host project builds and provides ai_profile.
    VisionDirector consumes that profile but does not instantiate provider
    clients independently.

    This file is customer-owned after creation.
    smx-visiondirector will not overwrite it.
    """
    return _setup_visiondirector(
        app=app,
        project_root=PROJECT_ROOT,
        init_schema=init_schema,
        ai_profile=ai_profile,
    )
'''


    def _render_env_example_file() -> str:
        return '''# smx-visiondirector client project environment example

SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix
SMX_VISIONDIRECTOR_HOST_HOME_URL=/

SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector
SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector

SMX_VISIONDIRECTOR_ASSETS_DIR=./plugins/visiondirector/assets
SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png
SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png
'''


    def _render_runtime_env_file(*, assets_dir: Path) -> str:
        return f'''# smx-visiondirector local runtime environment
#
# This file is customer-owned after creation.
# smx-visiondirector will not overwrite it.

SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix
SMX_VISIONDIRECTOR_HOST_HOME_URL=/

SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector
SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector

SMX_VISIONDIRECTOR_ASSETS_DIR={_path_value(assets_dir)}
SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png
SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png
'''


    def _render_deploy_env_example_file() -> str:
        return '''# smx-visiondirector production deployment example

SMX_VISIONDIRECTOR_PUBLIC_BASE_URL=https://your-domain.com

SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix
SMX_VISIONDIRECTOR_HOST_HOME_URL=/

SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector
SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector

SMX_VISIONDIRECTOR_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/visiondirector/assets
SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png
SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png
'''
    """,
)

write_file(
    "src/smx_visiondirector/__init__.py",
    r"""
    from __future__ import annotations

    import json
    import os
    from pathlib import Path
    from typing import Any

    from flask import Blueprint, Response, send_from_directory, url_for

    from .smxcp import SmxVisionDirectorScaffold, ensure_visiondirector_scaffold


    __version__ = "0.1.0"

    PACKAGE_ROOT = Path(__file__).resolve().parent
    PROJECT_ROOT = PACKAGE_ROOT.parents[1]
    DEFAULT_URL_PREFIX = "/visiondirector"


    def create_visiondirector_blueprint(
        *,
        config: dict[str, Any] | None = None,
        project_root: str | Path | None = None,
        ai_profile: dict[str, Any] | None = None,
    ) -> Blueprint:
        resolved_config = config or {}
        resolved_project_root = Path(project_root or PROJECT_ROOT).resolve()

        bp = Blueprint("smx_visiondirector", __name__)

        @bp.get("/health")
        def health():
            profile = ai_profile or {}
            return {
                "status": "ok",
                "package": "smx-visiondirector",
                "has_ai_profile": bool(profile),
                "has_main_profile": "main" in profile,
                "has_assistant_profile": "assistant" in profile,
            }

        @bp.get("/assets/<path:filename>")
        def asset(filename: str):
            assets_dir = Path(
                resolved_config.get("assets_dir")
                or "plugins/visiondirector/assets"
            )
            if not assets_dir.is_absolute():
                assets_dir = Path.cwd() / assets_dir
            return send_from_directory(assets_dir, filename)

        @bp.get("/")
        def home():
            index_file = resolved_project_root / "index.html"
            if not index_file.exists():
                return Response("VisionDirector index.html not found.", status=500)

            html = index_file.read_text(encoding="utf-8")
            html = _inject_safe_runtime(html, config=resolved_config, ai_profile=ai_profile)
            html = _rewrite_index_asset_urls(html)
            return Response(html, mimetype="text/html")

        @bp.get("/<path:filename>")
        def static_file(filename: str):
            return send_from_directory(resolved_project_root, filename)

        return bp


    def setup_visiondirector(
        app,
        *,
        project_root: str | Path | None = None,
        init_schema: bool = True,
        ai_profile: dict[str, Any] | None = None,
    ):
        scaffold = ensure_visiondirector_scaffold(project_root=project_root)
        config = _config_from_env_file(scaffold.env_file)

        return init_visiondirector(
            app,
            config=config,
            project_root=PROJECT_ROOT,
            init_schema=init_schema,
            ai_profile=ai_profile,
        )


    def init_visiondirector(
        app,
        *,
        config: dict[str, Any] | None = None,
        project_root: str | Path | None = None,
        init_schema: bool = False,
        ai_profile: dict[str, Any] | None = None,
    ):
        # init_schema is part of the SyntaxMatrix plugin contract.
        # VisionDirector has no package database schema yet, so this is a no-op.
        app.register_blueprint(
            create_visiondirector_blueprint(
                config=config,
                project_root=project_root,
                ai_profile=ai_profile,
            ),
            url_prefix=DEFAULT_URL_PREFIX,
        )
        return app


    def _config_from_env_file(env_file: str | Path) -> dict[str, str]:
        values: dict[str, str] = {}
        path = Path(env_file)

        if path.exists():
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = os.environ.get(key.strip(), value.strip())

        return {
            "host_site_title": values.get("SMX_VISIONDIRECTOR_HOST_SITE_TITLE", "SyntaxMatrix"),
            "host_home_url": values.get("SMX_VISIONDIRECTOR_HOST_HOME_URL", "/"),
            "app_title": values.get("SMX_VISIONDIRECTOR_APP_TITLE", "VisionDirector"),
            "app_home_url": values.get("SMX_VISIONDIRECTOR_APP_HOME_URL", DEFAULT_URL_PREFIX),
            "assets_dir": values.get("SMX_VISIONDIRECTOR_ASSETS_DIR", "plugins/visiondirector/assets"),
            "logo_url": values.get("SMX_VISIONDIRECTOR_LOGO_URL", "/visiondirector/assets/logo.png"),
            "favicon_url": values.get("SMX_VISIONDIRECTOR_FAVICON_URL", "/visiondirector/assets/favicon.png"),
        }


    def _inject_safe_runtime(
        html: str,
        *,
        config: dict[str, Any],
        ai_profile: dict[str, Any] | None,
    ) -> str:
        profile = ai_profile or {}
        runtime = {
            "appTitle": config.get("app_title") or "VisionDirector",
            "hostSiteTitle": config.get("host_site_title") or "SyntaxMatrix",
            "hostHomeUrl": config.get("host_home_url") or "/",
            "appHomeUrl": config.get("app_home_url") or DEFAULT_URL_PREFIX,
            "hasAiProfile": bool(profile),
            "hasMainProfile": "main" in profile,
            "hasAssistantProfile": "assistant" in profile,
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


    def _rewrite_index_asset_urls(html: str) -> str:
        css_url = url_for("smx_visiondirector.static_file", filename="index.css")
        js_url = url_for("smx_visiondirector.static_file", filename="index.js")

        return (
            html.replace('href="/index.css"', f'href="{css_url}"')
            .replace("href='/index.css'", f"href='{css_url}'")
            .replace('src="/index.js"', f'src="{js_url}"')
            .replace("src='/index.js'", f"src='{js_url}'")
        )


    __all__ = [
        "DEFAULT_URL_PREFIX",
        "PACKAGE_ROOT",
        "PROJECT_ROOT",
        "SmxVisionDirectorScaffold",
        "__version__",
        "create_visiondirector_blueprint",
        "ensure_visiondirector_scaffold",
        "init_visiondirector",
        "setup_visiondirector",
    ]
    """,
)

write_file(
    "tests/test_editable_package_contract.py",
    """
    from __future__ import annotations

    from importlib.metadata import version

    import smx_visiondirector


    def test_package_imports_from_editable_install():
        assert smx_visiondirector.__version__ == "0.1.0"


    def test_distribution_metadata_is_available():
        assert version("smx-visiondirector") == "0.1.0"


    def test_project_root_points_to_visiondirector_root():
        assert (smx_visiondirector.PROJECT_ROOT / "index.html").exists()
        assert (smx_visiondirector.PROJECT_ROOT / "index.js").exists()
    """,
)

write_file(
    "tests/test_smxcp_contract.py",
    """
    from __future__ import annotations

    from smx_visiondirector.smxcp import (
        _render_setup_file,
        ensure_visiondirector_scaffold,
    )


    def test_smxcp_creates_customer_owned_scaffold(tmp_path):
        scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)

        assert scaffold.scaffold_dir == tmp_path / "plugins" / "visiondirector"
        assert scaffold.setup_file.exists()
        assert scaffold.env_file.exists()
        assert scaffold.env_example_file.exists()
        assert scaffold.deploy_env_example_file.exists()
        assert scaffold.data_dir.exists()
        assert scaffold.assets_dir.exists()
        assert scaffold.logo_file.exists()
        assert scaffold.favicon_file.exists()


    def test_smxcp_does_not_overwrite_customer_owned_setup_file(tmp_path):
        scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)
        scaffold.setup_file.write_text("# customer change", encoding="utf-8")

        ensure_visiondirector_scaffold(project_root=tmp_path)

        assert scaffold.setup_file.read_text(encoding="utf-8") == "# customer change"


    def test_smxcp_setup_file_passes_host_built_ai_profile():
        content = _render_setup_file()

        assert "def setup_visiondirector(app, *, init_schema: bool = True, ai_profile=None):" in content
        assert "from smx_visiondirector import setup_visiondirector as _setup_visiondirector" in content
        assert "project_root=PROJECT_ROOT" in content
        assert "ai_profile=ai_profile" in content


    def test_smxcp_setup_file_does_not_build_provider_profile():
        content = _render_setup_file()

        assert "from google import genai" not in content
        assert "from dotenv import load_dotenv" not in content
        assert "GOOGLE_API_KEY" not in content
        assert "OPENAI_API_KEY" not in content
        assert "_build_ai_profile" not in content
    """,
)

write_file(
    "tests/test_smx_visiondirector_plugin_contract.py",
    """
    from __future__ import annotations

    from flask import Flask

    import smx_visiondirector
    from smx_visiondirector import setup_visiondirector


    def test_setup_visiondirector_is_public_api():
        assert callable(setup_visiondirector)
        assert smx_visiondirector.DEFAULT_URL_PREFIX == "/visiondirector"


    def test_setup_registers_namespaced_health_route(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            init_schema=True,
            ai_profile={
                "main": {"provider": "google", "api_key": "secret-main"},
                "assistant": {"provider": "openai", "api_key": "secret-assistant"},
            },
        )

        response = app.test_client().get("/visiondirector/health")

        assert response.status_code == 200
        assert response.get_json() == {
            "status": "ok",
            "package": "smx-visiondirector",
            "has_ai_profile": True,
            "has_main_profile": True,
            "has_assistant_profile": True,
        }


    def test_home_serves_index_under_namespace(tmp_path):
        app = Flask(__name__)
        setup_visiondirector(app, project_root=tmp_path)

        response = app.test_client().get("/visiondirector/")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "VisionDirector Elite" in body
        assert 'href="/visiondirector/index.css"' in body
        assert 'src="/visiondirector/index.js"' in body


    def test_home_does_not_expose_provider_api_keys(tmp_path):
        app = Flask(__name__)

        setup_visiondirector(
            app,
            project_root=tmp_path,
            ai_profile={
                "main": {
                    "provider": "google",
                    "api_key": "SHOULD_NOT_LEAK",
                }
            },
        )

        response = app.test_client().get("/visiondirector/")

        assert response.status_code == 200
        assert "SHOULD_NOT_LEAK" not in response.get_data(as_text=True)
    """,
)

print("\nPatch complete: VisionDirector now exposes smx_visiondirector and smxcp inside the plugin package only.")
