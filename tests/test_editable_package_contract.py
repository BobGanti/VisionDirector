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
