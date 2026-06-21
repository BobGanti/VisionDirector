from pathlib import Path

replacements = {
    "tests/test_ai_generate_image_route.py": {
        '"model": "gemini-image-model",': '"model": "gemini-2.5-flash-image",',
        'assert client.models.calls[0]["model"] == "gemini-image-model"': 'assert client.models.calls[0]["model"] == "gemini-2.5-flash-image"',
    },
    "tests/test_ai_parse_script_route.py": {
        '"model": "gemini-2.5-flash",': '"model": "gemini-3-flash-preview",',
        'assert client.models.calls[0]["model"] == "gemini-2.5-flash"': 'assert client.models.calls[0]["model"] == "gemini-3-flash-preview"',
    },
}

for file_name, file_replacements in replacements.items():
    path = Path(file_name)
    text = path.read_text(encoding="utf-8")
    for old, new in file_replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"updated {file_name}")

print("fixed old tests to expect current-effective task models")
