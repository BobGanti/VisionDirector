from __future__ import annotations

from pathlib import Path

root = Path.cwd()
init_file = root / "src" / "smx_visiondirector" / "__init__.py"
pytest_ini = root / "pytest.ini"

content = init_file.read_text(encoding="utf-8")

if "def init_visiondirector(" not in content:
    marker = '''def setup_visiondirector(app, **kwargs):
    """
    Register VisionDirector on a host Flask app.

    This is the public integration API used by SyntaxMatrix host projects.
    It creates the VisionDirector blueprint, registers it under the plugin
    root path, and returns the registered blueprint.
    """
    url_prefix = str(kwargs.pop("url_prefix", DEFAULT_URL_PREFIX))
    blueprint = create_visiondirector_blueprint(**kwargs)
    app.register_blueprint(blueprint, url_prefix=url_prefix)
    return blueprint
'''
    if marker not in content:
        raise SystemExit("Could not find exact setup_visiondirector function block.")

    replacement = marker + '''

def init_visiondirector(app, **kwargs):
    """
    Backward-compatible alias for older VisionDirector tests and integrations.

    New SyntaxMatrix plugin integrations should use setup_visiondirector(...).
    """
    return setup_visiondirector(app, **kwargs)
'''
    content = content.replace(marker, replacement, 1)
    init_file.write_text(content, encoding="utf-8")
    print("Added backward-compatible init_visiondirector alias.")
else:
    print("init_visiondirector alias already present.")

pytest_ini.write_text(
    """[pytest]
testpaths = tests
norecursedirs =
    VisionDirector
    .git
    .venv
    venv
    patches
    build
    dist
""",
    encoding="utf-8",
)
print("Wrote pytest.ini to restrict collection to top-level tests/.")
