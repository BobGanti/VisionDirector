from __future__ import annotations

from pathlib import Path
from textwrap import dedent


ROOT = Path.cwd()

REQUIRED_ROOT_FILES = [
    "app.py",
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
    "pyproject.toml",
    """
    [build-system]
    requires = ["setuptools>=69", "wheel"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "vision-director"
    version = "0.1.0"
    description = "VisionDirector plugin module for SyntaxMatrix host applications."
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

    VisionDirector is being prepared as a pluggable SyntaxMatrix module.

    This package is installed into a host application's virtual environment in editable mode during development:

    ```powershell
    python -m pip install -e ../VisionDirector
    ```

    The host framework will later initialize it through a small customer-owned setup file under `plugins/vision_director/`.
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

    __all__ = [
        "PACKAGE_ROOT",
        "PROJECT_ROOT",
        "__version__",
    ]
    """,
)

write_file(
    "tests/test_editable_package_contract.py",
    """
    from __future__ import annotations

    from importlib.metadata import version

    import vision_director


    def test_package_imports_from_editable_install():
        assert vision_director.__version__ == "0.1.0"


    def test_distribution_metadata_is_available():
        assert version("vision-director") == "0.1.0"


    def test_project_root_points_to_visiondirector_root():
        root = vision_director.PROJECT_ROOT
        assert (root / "app.py").exists()
        assert (root / "index.html").exists()
    """,
)

print("\nStep 1 complete: VisionDirector now has editable package metadata and an importable vision_director package.")
