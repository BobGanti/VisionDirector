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
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _write_bytes_if_missing(path: Path, content: bytes) -> None:
    if not path.exists():
        path.write_bytes(content)


def _path_value(path: Path) -> str:
    return path.resolve().as_posix()


def _render_setup_file() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n"
        "from smx_visiondirector import setup_visiondirector as _setup_visiondirector\n\n\n"
        "PROJECT_ROOT = Path(__file__).resolve().parents[2]\n\n\n"
        "def setup_visiondirector(app, *, init_schema: bool = True, ai_profile=None):\n"
        "    # Customer-owned connector. Host builds and passes ai_profile.\n"
        "    return _setup_visiondirector(\n"
        "        app=app,\n"
        "        project_root=PROJECT_ROOT,\n"
        "        init_schema=init_schema,\n"
        "        ai_profile=ai_profile,\n"
        "    )\n"
    )


def _render_env_example_file() -> str:
    return (
        "# smx-visiondirector client project environment example\n\n"
        "SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix\n"
        "SMX_VISIONDIRECTOR_HOST_HOME_URL=/\n\n"
        "SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector\n"
        "SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector\n\n"
        "SMX_VISIONDIRECTOR_ASSETS_DIR=./plugins/visiondirector/assets\n"
        "SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png\n"
        "SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\n"
    )


def _render_runtime_env_file(*, assets_dir: Path) -> str:
    return (
        "# smx-visiondirector local runtime environment\n"
        "# Customer-owned. The package will not overwrite this file.\n\n"
        "SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix\n"
        "SMX_VISIONDIRECTOR_HOST_HOME_URL=/\n\n"
        "SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector\n"
        "SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector\n\n"
        f"SMX_VISIONDIRECTOR_ASSETS_DIR={_path_value(assets_dir)}\n"
        "SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png\n"
        "SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\n"
    )


def _render_deploy_env_example_file() -> str:
    return (
        "# smx-visiondirector production deployment example\n\n"
        "SMX_VISIONDIRECTOR_PUBLIC_BASE_URL=https://your-domain.com\n\n"
        "SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix\n"
        "SMX_VISIONDIRECTOR_HOST_HOME_URL=/\n\n"
        "SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector\n"
        "SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector\n\n"
        "SMX_VISIONDIRECTOR_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/visiondirector/assets\n"
        "SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png\n"
        "SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\n"
    )
