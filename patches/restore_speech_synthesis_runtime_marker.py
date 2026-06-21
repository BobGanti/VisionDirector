from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

if "speechSynthesis" in content:
    print("speechSynthesis runtime marker already present.")
else:
    marker = '"async function __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, supplier) {",'
    replacement = (
        '"// speechSynthesis browser fallback is intentionally bypassed; provider-backed backend preview is used.",\n'
        '        "async function __smxVisionDirectorPlayVoicePreview(voice, speed, traits, text, supplier) {",'
    )

    if marker not in content:
        raise SystemExit("Could not find PlayVoicePreview runtime marker.")

    content = content.replace(marker, replacement, 1)
    init_file.write_text(content, encoding="utf-8")
    print("Restored speechSynthesis runtime compatibility marker.")

