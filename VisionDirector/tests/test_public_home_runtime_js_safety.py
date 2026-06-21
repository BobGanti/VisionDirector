from __future__ import annotations

from flask import Flask

from smx_visiondirector import setup_visiondirector


def test_public_home_serves_html_with_namespaced_bundle(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "VisionDirector Elite" in body
    assert 'src="/visiondirector/index.js"' in body
    assert 'href="/visiondirector/index.css"' in body


def test_runtime_js_patch_uses_real_newlines_not_literal_backslash_n(tmp_path):
    app = Flask(__name__)
    setup_visiondirector(app, project_root=tmp_path)

    response = app.test_client().get("/visiondirector/index.js")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "__smxVisionDirectorParseScript" in body
    assert "__smxVisionDirectorGenerateImage" in body
    assert "\\n// smx-visiondirector host AI patch." not in body
    assert "\n// smx-visiondirector host AI patch." in body
