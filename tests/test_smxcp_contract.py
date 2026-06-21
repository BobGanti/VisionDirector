from __future__ import annotations

from smx_visiondirector.smxcp import (
    _render_deploy_env_example_file,
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



def _png_dimensions(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
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



def test_smxcp_local_env_contains_admin_token(tmp_path):
    scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)

    content = scaffold.env_file.read_text(encoding="utf-8")

    assert "SMX_VISIONDIRECTOR_ADMIN_TOKEN=local-visiondirector-admin-token" in content


def test_smxcp_deploy_env_example_contains_admin_token_secret_mapping(tmp_path):
    scaffold = ensure_visiondirector_scaffold(project_root=tmp_path)

    content = scaffold.deploy_env_example_file.read_text(encoding="utf-8")

    assert "SMX_VISIONDIRECTOR_ADMIN_TOKEN=visiondirector-admin-token-secret-vault:latest" in content
