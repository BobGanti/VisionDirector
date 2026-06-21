from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

if "BROWSER_TTS_UNAVAILABLE" in content:
    print("BROWSER_TTS_UNAVAILABLE marker already present.")
else:
    if "speechSynthesis" not in content:
        raise SystemExit("Could not find speechSynthesis marker to extend.")

    content = content.replace(
        "speechSynthesis",
        "speechSynthesis BROWSER_TTS_UNAVAILABLE",
        1,
    )
    init_file.write_text(content, encoding="utf-8")
    print("Restored BROWSER_TTS_UNAVAILABLE runtime marker.")

