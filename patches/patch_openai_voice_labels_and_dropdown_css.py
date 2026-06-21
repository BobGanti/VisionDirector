from __future__ import annotations

from pathlib import Path
import re
from textwrap import dedent

ROOT = Path.cwd()
SANDBOX_ROOT = ROOT.parent / "vision-director-sandbox"

OPENAI_TS_BLOCK = """export const OPENAI_VOICES: { id: VoiceProfile; label: string }[] = [
  // UI voice-presentation labels. Provider voice names remain unchanged.
  { id: 'alloy', label: 'ALLOY (F)' },
  { id: 'echo', label: 'ECHO (M)' },
  { id: 'fable', label: 'FABLE (M)' },
  { id: 'onyx', label: 'ONYX (M)' },
  { id: 'nova', label: 'NOVA (F)' },
  { id: 'shimmer', label: 'SHIMMER (F)' },
  { id: 'verse', label: 'VERSE (M)' },
  { id: 'ash', label: 'ASH (M)' },
  { id: 'sage', label: 'SAGE (F)' },
  { id: 'ballad', label: 'BALLAD (M)' },
  { id: 'coral', label: 'CORAL (F)' },
];

"""

OPENAI_JS_BLOCK = """var OPENAI_VOICES = [
  // UI voice-presentation labels. Provider voice names remain unchanged.
  { id: "alloy", label: "ALLOY (F)" },
  { id: "echo", label: "ECHO (M)" },
  { id: "fable", label: "FABLE (M)" },
  { id: "onyx", label: "ONYX (M)" },
  { id: "nova", label: "NOVA (F)" },
  { id: "shimmer", label: "SHIMMER (F)" },
  { id: "verse", label: "VERSE (M)" },
  { id: "ash", label: "ASH (M)" },
  { id: "sage", label: "SAGE (F)" },
  { id: "ballad", label: "BALLAD (M)" },
  { id: "coral", label: "CORAL (F)" }
];
"""

DROPDOWN_CSS = dedent(
    """

    /* smx-visiondirector native dropdown option readability */
    .vd-ui select option {
      color: #111827 !important;
      background-color: #ffffff !important;
      font-weight: 700;
    }

    .vd-ui select option:checked {
      color: #ffffff !important;
      background-color: #6d28d9 !important;
    }

    .vd-ui select option:hover {
      color: #111827 !important;
      background-color: #e5e7eb !important;
    }
    """
)


def patch_studio_tsx(project_root: Path) -> None:
    path = project_root / "components" / "Studio.tsx"
    if not path.exists():
        print(f"skip missing {path}")
        return

    text = path.read_text(encoding="utf-8")
    pattern = r"export const OPENAI_VOICES: \{ id: VoiceProfile; label: string \}\[\] = \[[\s\S]*?\];\n\nexport const SUPPLIERS:"
    replacement = OPENAI_TS_BLOCK + "export const SUPPLIERS:"

    new_text, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        if "ALLOY (F)" in text and "CORAL (F)" in text:
            print(f"already patched {path}")
            return
        raise SystemExit(f"Could not patch OpenAI voices in {path}")

    path.write_text(new_text, encoding="utf-8")
    print(f"patched {path}")


def patch_index_js(project_root: Path) -> None:
    path = project_root / "index.js"
    if not path.exists():
        print(f"skip missing {path}")
        return

    text = path.read_text(encoding="utf-8")
    pattern = r"var OPENAI_VOICES = \[[\s\S]*?\];\nvar SUPPLIERS ="
    replacement = OPENAI_JS_BLOCK + "var SUPPLIERS ="

    new_text, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        if "ALLOY (F)" in text and "CORAL (F)" in text:
            print(f"already patched {path}")
            return
        raise SystemExit(f"Could not patch OpenAI voices in {path}")

    path.write_text(new_text, encoding="utf-8")
    print(f"patched {path}")


def patch_index_css(project_root: Path) -> None:
    path = project_root / "index.css"
    if not path.exists():
        print(f"skip missing {path}")
        return

    text = path.read_text(encoding="utf-8")
    if "smx-visiondirector native dropdown option readability" in text:
        print(f"already patched {path}")
        return

    path.write_text(text.rstrip() + DROPDOWN_CSS + "\n", encoding="utf-8")
    print(f"patched {path}")


for project in [ROOT, SANDBOX_ROOT]:
    patch_studio_tsx(project)
    patch_index_js(project)
    patch_index_css(project)


test_file = ROOT / "tests" / "test_frontend_voice_labels_and_select_css.py"
test_file.write_text(
    dedent(
        '''
        from __future__ import annotations

        from pathlib import Path


        OPENAI_LABELS = [
            "ALLOY (F)",
            "ECHO (M)",
            "FABLE (M)",
            "ONYX (M)",
            "NOVA (F)",
            "SHIMMER (F)",
            "VERSE (M)",
            "ASH (M)",
            "SAGE (F)",
            "BALLAD (M)",
            "CORAL (F)",
        ]


        def test_openai_voice_labels_include_gender_markers_in_source_and_bundle():
            studio = Path("components/Studio.tsx").read_text(encoding="utf-8")
            bundle = Path("index.js").read_text(encoding="utf-8")

            for label in OPENAI_LABELS:
                assert label in studio
                assert label in bundle


        def test_native_dropdown_options_have_readable_text_colors():
            css = Path("index.css").read_text(encoding="utf-8")

            assert "smx-visiondirector native dropdown option readability" in css
            assert ".vd-ui select option" in css
            assert "color: #111827" in css
            assert "background-color: #ffffff" in css
            assert ".vd-ui select option:checked" in css
        '''
    ).lstrip(),
    encoding="utf-8",
)

print("patched frontend tests")
