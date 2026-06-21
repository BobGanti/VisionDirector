from __future__ import annotations

from pathlib import Path
from textwrap import dedent
import re

ROOT = Path.cwd()
smxcp_file = ROOT / "src" / "smx_visiondirector" / "smxcp.py"
pyproject_file = ROOT / "pyproject.toml"
test_file = ROOT / "tests" / "test_smxcp_contract.py"
default_assets_dir = ROOT / "src" / "smx_visiondirector" / "default_assets"

default_assets_dir.mkdir(parents=True, exist_ok=True)
(default_assets_dir / ".gitkeep").write_text(
    "Plugin developers may place default logo.png and favicon.png here.\n"
    "If either file is missing or empty, smxCP generates shaded PNG fallback assets.\n",
    encoding="utf-8",
)

content = smxcp_file.read_text(encoding="utf-8")

if "import struct" not in content:
    content = content.replace("from __future__ import annotations\n\n", "from __future__ import annotations\n\nimport struct\nimport zlib\n", 1)

if "DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent / \"default_assets\"" not in content:
    anchor = 'ASSETS_DIR_NAME = "assets"\n'
    insert = (
        'ASSETS_DIR_NAME = "assets"\n'
        'DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent / "default_assets"\n'
        "DEFAULT_LOGO_SIZE = 512\n"
        "DEFAULT_FAVICON_SIZE = 32\n"
    )
    content = content.replace(anchor, insert, 1)

content = content.replace(
    "_write_bytes_if_missing(logo_file, FALLBACK_PNG_BYTES)\n"
    "    _write_bytes_if_missing(favicon_file, FALLBACK_PNG_BYTES)\n",
    "_write_default_asset_if_missing_or_empty(logo_file, filename=\"logo.png\", size=DEFAULT_LOGO_SIZE)\n"
    "    _write_default_asset_if_missing_or_empty(favicon_file, filename=\"favicon.png\", size=DEFAULT_FAVICON_SIZE)\n",
)

if "def _write_default_asset_if_missing_or_empty(" not in content:
    anchor = (
        "def _write_bytes_if_missing(path: Path, content: bytes) -> None:\n"
        "    if not path.exists():\n"
        "        path.write_bytes(content)\n"
    )
    helpers = dedent(
        '''


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
                + b"\\x08\\x06\\x00\\x00\\x00"
            )
            return (
                b"\\x89PNG\\r\\n\\x1a\\n"
                + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
                + chunk(b"IEND", b"")
            )
        '''
    )
    content = content.replace(anchor, anchor + helpers, 1)

deploy_start = content.find("def _render_deploy_env_example_file() -> str:")
if deploy_start < 0:
    raise SystemExit("Could not find _render_deploy_env_example_file.")

deploy_func = dedent(
    '''
    def _render_deploy_env_example_file() -> str:
        return (
            "# smx-visiondirector production deployment example\\n"
            "#\\n"
            "# Purpose:\\n"
            "# - Copy these variable names into your Cloud Run deployment script.\\n"
            "# - Replace placeholder values with your client/project values.\\n"
            "# - Do not put raw secret values in this file.\\n"
            "#\\n"
            "# Local development runtime config:\\n"
            "#   plugins/visiondirector/.smx_visiondirector.env\\n"
            "#\\n"
            "# Production deployment example:\\n"
            "#   plugins/visiondirector/.smx_visiondirector.deploy_example.env\\n"
            "#\\n"
            "# smxCP rule:\\n"
            "#   one Secret Manager vault -> one SMX_VISIONDIRECTOR_* Cloud Run env var\\n\\n\\n"
            "# ---------------------------------------------------------------------\\n"
            "# Required production non-secret env vars\\n"
            "# Use these with: gcloud run deploy/update --set-env-vars\\n"
            "# ---------------------------------------------------------------------\\n\\n"
            "SMX_VISIONDIRECTOR_PUBLIC_BASE_URL=https://your-domain.com\\n"
            "SMX_VISIONDIRECTOR_HOST_SITE_TITLE=SyntaxMatrix\\n"
            "SMX_VISIONDIRECTOR_HOST_HOME_URL=/\\n"
            "SMX_VISIONDIRECTOR_APP_TITLE=VisionDirector\\n"
            "SMX_VISIONDIRECTOR_APP_HOME_URL=/visiondirector\\n\\n"
            "SMX_VISIONDIRECTOR_DATABASE_BACKEND=postgresql\\n"
            "SMX_VISIONDIRECTOR_DB_USER=your_visiondirector_db_user\\n"
            "SMX_VISIONDIRECTOR_DB_NAME=your_visiondirector_db_name\\n"
            "SMX_VISIONDIRECTOR_INSTANCE_CONNECTION_NAME=your-project:your-region:your-cloudsql-instance\\n"
            "SMX_VISIONDIRECTOR_AUTO_INIT=1\\n\\n"
            "SMX_VISIONDIRECTOR_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/visiondirector/assets\\n"
            "SMX_VISIONDIRECTOR_DATA_DIR=/app/$LOCAL_DATA_SOURCE/plugins/visiondirector/data\\n"
            "SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png\\n"
            "SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png\\n\\n\\n"
            "# ---------------------------------------------------------------------\\n"
            "# Required production secret mappings\\n"
            "# Use these with: gcloud run deploy/update --set-secrets\\n"
            "#\\n"
            "# Format:\\n"
            "#   CLOUD_RUN_ENV_VAR=secret-manager-vault-name:latest\\n"
            "# ---------------------------------------------------------------------\\n\\n"
            "SMX_VISIONDIRECTOR_DATABASE_URL=visiondirector-database-url-secret-vault:latest\\n\\n\\n"
            "# ---------------------------------------------------------------------\\n"
            "# Required host AI provider configuration\\n"
            "# ---------------------------------------------------------------------\\n"
            "# VisionDirector does not instantiate provider clients independently.\\n"
            "# The SyntaxMatrix host must build and pass ai_profile with provider clients.\\n"
            "# Typical production providers are configured in the host agency/database layer,\\n"
            "# not inside this plugin env file.\\n\\n\\n"
            "# ---------------------------------------------------------------------\\n"
            "# Required Cloud Run storage mount\\n"
            "# ---------------------------------------------------------------------\\n\\n"
            "SMX_CLIENT_DIR=/app/$LOCAL_DATA_SOURCE\\n"
            "GCS_MOUNT_PATH=/app/$LOCAL_DATA_SOURCE\\n"
            "SMX_VISIONDIRECTOR_ASSETS_BUCKET_PREFIX=plugins/visiondirector/assets\\n"
            "SMX_VISIONDIRECTOR_DATA_BUCKET_PREFIX=plugins/visiondirector/data\\n\\n\\n"
            "# ---------------------------------------------------------------------\\n"
            "# Production database note\\n"
            "# ---------------------------------------------------------------------\\n"
            "# The plugin reads SMX_VISIONDIRECTOR_DATABASE_URL for persistent storage.\\n"
            "# Local development may continue to use SQLite under plugins/visiondirector/data.\\n"
            "# Production deployments should use a dedicated VisionDirector PostgreSQL database.\\n"
        )
    '''
).lstrip()

content = content[:deploy_start] + deploy_func
smxcp_file.write_text(content, encoding="utf-8")
print("patched smxcp assets and deploy env example")


pyproject = pyproject_file.read_text(encoding="utf-8")
old_package_data = 'smx_visiondirector = ["static/*.css"]'
new_package_data = 'smx_visiondirector = ["static/*.css", "default_assets/*.png"]'
if old_package_data in pyproject:
    pyproject = pyproject.replace(old_package_data, new_package_data, 1)
elif new_package_data in pyproject:
    pass
else:
    raise SystemExit("Could not find smx_visiondirector package-data line.")
pyproject_file.write_text(pyproject, encoding="utf-8")
print("patched pyproject package-data for optional default assets")


tests = test_file.read_text(encoding="utf-8")

tests = tests.replace(
    "from smx_visiondirector.smxcp import (\n"
    "    _render_setup_file,\n"
    "    ensure_visiondirector_scaffold,\n"
    ")\n",
    "from smx_visiondirector.smxcp import (\n"
    "    _render_deploy_env_example_file,\n"
    "    _render_setup_file,\n"
    "    ensure_visiondirector_scaffold,\n"
    ")\n",
)

if "def _png_dimensions(" not in tests:
    tests += dedent(
        '''


        def _png_dimensions(data: bytes) -> tuple[int, int]:
            assert data.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
            return (
                int.from_bytes(data[16:20], "big"),
                int.from_bytes(data[20:24], "big"),
            )


        def test_smxcp_creates_non_empty_default_brand_assets_with_expected_sizes(tmp_path):
            scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)

            logo_bytes = scaffold.logo_file.read_bytes()
            favicon_bytes = scaffold.favicon_file.read_bytes()

            assert len(logo_bytes) > 100
            assert len(favicon_bytes) > 50
            assert _png_dimensions(logo_bytes) == (512, 512)
            assert _png_dimensions(favicon_bytes) == (32, 32)


        def test_smxcp_replaces_empty_default_brand_assets(tmp_path):
            assets_dir = tmp_path / "plugins" / "visiondirector" / "assets"
            assets_dir.mkdir(parents=True)
            (assets_dir / "logo.png").write_bytes(b"")
            (assets_dir / "favicon.png").write_bytes(b"")

            scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)

            assert scaffold.logo_file.stat().st_size > 100
            assert scaffold.favicon_file.stat().st_size > 50
            assert _png_dimensions(scaffold.logo_file.read_bytes()) == (512, 512)
            assert _png_dimensions(scaffold.favicon_file.read_bytes()) == (32, 32)


        def test_smxcp_deploy_env_example_documents_postgres_and_cloud_run_storage():
            content = _render_deploy_env_example_file()

            assert "SMX_VISIONDIRECTOR_DATABASE_BACKEND=postgresql" in content
            assert "SMX_VISIONDIRECTOR_DB_USER=your_visiondirector_db_user" in content
            assert "SMX_VISIONDIRECTOR_DB_NAME=your_visiondirector_db_name" in content
            assert "SMX_VISIONDIRECTOR_INSTANCE_CONNECTION_NAME=your-project:your-region:your-cloudsql-instance" in content
            assert "SMX_VISIONDIRECTOR_DATABASE_URL=visiondirector-database-url-secret-vault:latest" in content
            assert "SMX_VISIONDIRECTOR_AUTO_INIT=1" in content
            assert "SMX_CLIENT_DIR=/app/$LOCAL_DATA_SOURCE" in content
            assert "GCS_MOUNT_PATH=/app/$LOCAL_DATA_SOURCE" in content
            assert "SMX_VISIONDIRECTOR_ASSETS_BUCKET_PREFIX=plugins/visiondirector/assets" in content
            assert "SMX_VISIONDIRECTOR_DATA_BUCKET_PREFIX=plugins/visiondirector/data" in content
            assert "SMX_VISIONDIRECTOR_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/visiondirector/assets" in content
            assert "SMX_VISIONDIRECTOR_LOGO_URL=/visiondirector/assets/logo.png" in content
            assert "SMX_VISIONDIRECTOR_FAVICON_URL=/visiondirector/assets/favicon.png" in content
        '''
    )

test_file.write_text(tests, encoding="utf-8")
print("patched smxCP tests")
