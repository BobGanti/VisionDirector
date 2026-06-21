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
