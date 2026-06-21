from __future__ import annotations

import struct
import zlib
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
DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent / "default_assets"
DEFAULT_LOGO_SIZE = 512
DEFAULT_FAVICON_SIZE = 32

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
    _append_env_line_if_missing(
        env_example_file,
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=replace-with-local-admin-token",
    )
    _append_env_line_if_missing(
        env_file,
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=local-visiondirector-admin-token",
    )
    _append_env_line_if_missing(
        deploy_env_example_file,
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN",
        "SMX_VISIONDIRECTOR_ADMIN_TOKEN=visiondirector-admin-token-secret-vault:latest",
    )
    _write_default_asset_if_missing_or_empty(logo_file, filename="logo.png", size=DEFAULT_LOGO_SIZE)
    _write_default_asset_if_missing_or_empty(favicon_file, filename="favicon.png", size=DEFAULT_FAVICON_SIZE)

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



def _append_env_line_if_missing(path: Path, key: str, line: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if f"{key}=" in existing:
        return

    separator = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(
        existing + separator + line.rstrip() + "\n",
        encoding="utf-8",
    )



def _write_default_asset_if_missing_or_empty(path: Path, *, filename: str, size: int) -> None:
    if path.exists() and path.stat().st_size > 0:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_default_asset_bytes(filename=filename, size=size))


def _default_asset_bytes(*, filename: str, size: int) -> bytes:
    packaged_asset = DEFAULT_ASSETS_DIR / filename
    if packaged_asset.exists() and packaged_asset.stat().st_size > 0:
        return packaged_asset.read_bytes()

    return _generate_shaded_square_png(size=size)


def _generate_shaded_square_png(*, size: int) -> bytes:
    if size <= 0:
        raise ValueError("PNG size must be greater than zero")

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return (
            len(data).to_bytes(4, "big")
            + kind
            + data
            + checksum.to_bytes(4, "big")
        )

    denominator = max(1, (size - 1) * 2)
    rows = bytearray()

    for y in range(size):
        rows.append(0)
        for x in range(size):
            shade = 34 + int(82 * ((x + y) / denominator))
            accent = 116 + int(68 * (x / max(1, size - 1)))
            rows.extend((shade, accent, 210, 255))

    ihdr = (
        size.to_bytes(4, "big")
        + size.to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + chunk(b"IEND", b"")
    )


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
    return """# smx-visiondirector local development example
#
# Copy this file to:
#   plugins/visiondirector/.smx_visiondirector.env
#
# Do not commit real secrets.

SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix
SMX_VISIONDIRECTOR_HOST_HOME_URL=/
SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector
SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector

SMX_VISIONDIRECTOR_DATABASE_BACKEND=sqlite
SMX_VISIONDIRECTOR_AUTO_INIT=1

SMX_VISIONDIRECTOR_ASSETS_DIR=plugins/visiondirector/assets
SMX_VISIONDIRECTOR_DATA_DIR=plugins/visiondirector/data
SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png
SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png

# Local admin access
SMX_VISIONDIRECTOR_ADMIN_TOKEN=replace-with-local-admin-token
"""

def _render_runtime_env_file(*, assets_dir: Path | None = None) -> str:
    return """# smx-visiondirector local runtime config
#
# This file is generated by smxCP for local development.
# Replace values as needed. Do not commit real secrets.

SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix
SMX_VISIONDIRECTOR_HOST_HOME_URL=/
SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector
SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector

SMX_VISIONDIRECTOR_DATABASE_BACKEND=sqlite
SMX_VISIONDIRECTOR_AUTO_INIT=1

SMX_VISIONDIRECTOR_ASSETS_DIR=plugins/visiondirector/assets
SMX_VISIONDIRECTOR_DATA_DIR=plugins/visiondirector/data
SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png
SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png

# Local admin access
SMX_VISIONDIRECTOR_ADMIN_TOKEN=local-visiondirector-admin-token
"""

def _render_deploy_env_example_file() -> str:
    return """# smx-visiondirector production deployment example
#
# Purpose:
# - Copy these variable names into your Cloud Run deployment script.
# - Replace placeholder values with your client/project values.
# - Do not put raw secret values in this file.
#
# Local development runtime config:
#   plugins/visiondirector/.smx_visiondirector.env
#
# Production deployment example:
#   plugins/visiondirector/.smx_visiondirector.deploy_example.env
#
# smxCP rule:
#   one Secret Manager vault -> one SMX_VISIONDIRECTOR_* Cloud Run env var


# ---------------------------------------------------------------------
# Required production non-secret env vars
# Use these with: gcloud run deploy/update --set-env-vars
# ---------------------------------------------------------------------

SMX_VISIONDIRECTOR_PUBLIC_BASE_URL=https://your-domain.com
SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix
SMX_VISIONDIRECTOR_HOST_HOME_URL=/
SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector
SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector

SMX_VISIONDIRECTOR_DATABASE_BACKEND=postgresql
SMX_VISIONDIRECTOR_DB_USER=your_visiondirector_db_user
SMX_VISIONDIRECTOR_DB_NAME=your_visiondirector_db_name
SMX_VISIONDIRECTOR_INSTANCE_CONNECTION_NAME=your-project:your-region:your-cloudsql-instance
SMX_VISIONDIRECTOR_AUTO_INIT=1

SMX_VISIONDIRECTOR_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/visiondirector/assets
SMX_VISIONDIRECTOR_DATA_DIR=/app/$LOCAL_DATA_SOURCE/plugins/visiondirector/data
SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png
SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png


# ---------------------------------------------------------------------
# Required production secret mappings
# Use these with: gcloud run deploy/update --set-secrets
#
# Format:
#   CLOUD_RUN_ENV_VAR=secret-manager-vault-name:latest
# ---------------------------------------------------------------------

SMX_VISIONDIRECTOR_DATABASE_URL=visiondirector-database-url-secret-vault:latest
SMX_VISIONDIRECTOR_ADMIN_TOKEN=visiondirector-admin-token-secret-vault:latest


# ---------------------------------------------------------------------
# Required host AI provider configuration
# ---------------------------------------------------------------------
# VisionDirector does not instantiate provider clients independently.
# The SyntaxMatrix host must build and pass ai_profile with provider clients.
# Typical production providers are configured in the host agency/database layer,
# not inside this plugin env file.


# ---------------------------------------------------------------------
# Required Cloud Run storage mount
# ---------------------------------------------------------------------

SMX_CLIENT_DIR=/app/$LOCAL_DATA_SOURCE
GCS_MOUNT_PATH=/app/$LOCAL_DATA_SOURCE
SMX_VISIONDIRECTOR_ASSETS_BUCKET_PREFIX=plugins/visiondirector/assets
SMX_VISIONDIRECTOR_DATA_BUCKET_PREFIX=plugins/visiondirector/data


# ---------------------------------------------------------------------
# Production database note
# ---------------------------------------------------------------------
# The plugin reads SMX_VISIONDIRECTOR_DATABASE_URL for persistent storage.
# Local development may continue to use SQLite under plugins/visiondirector/data.
# Production deployments should use a dedicated VisionDirector PostgreSQL database.
"""

