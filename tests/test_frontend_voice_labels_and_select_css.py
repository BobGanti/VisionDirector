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
