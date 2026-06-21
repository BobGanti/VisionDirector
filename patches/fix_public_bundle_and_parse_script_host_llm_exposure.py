from pathlib import Path

# 1) Remove stale/dead key-vault wording from active served bundles.
root = Path("..").resolve()
skip_parts = {".git", "venv", ".venv", "node_modules", ".pytest_cache", "__pycache__", "patches"}

changed_js = []
for path in root.rglob("index.js"):
    if any(part in skip_parts for part in path.parts):
        continue

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    original = text
    text = text.replace(
        "Paste at least one key, then click Update Keys.",
        "Credentials are supplied by the SyntaxMatrix host.",
    )
    text = text.replace(
        'isSaved ? "Keys Updated" : "Update Keys"',
        'isSaved ? "Host Managed" : "Host Managed"',
    )

    if text != original:
        path.write_text(text, encoding="utf-8")
        changed_js.append(path)

print("Cleaned stale key-vault JS wording in:")
for path in changed_js:
    print(f"- {path}")


# 2) Parse-script is a host-owned LLM task.
#    It must ignore public payload model overrides and must not expose the host model name in the JSON response.
init_file = Path("src/smx_visiondirector/__init__.py")
text = init_file.read_text(encoding="utf-8")

old = '''        model = (
            str(payload.get("model") or "").strip()
            or _resolve_current_model("SCRIPT_PARSER", supplier)
        )
'''
new = '''        model = _resolve_current_model("SCRIPT_PARSER", supplier)
'''

if old not in text:
    raise SystemExit("Could not find parse-script model resolution block.")

text = text.replace(old, new, 1)

old = '''                "model": model,
'''
new = '''                "model": "host_llm",
'''
text = text.replace(old, new, 1)

old = '''            "model": result.model,
'''
new = '''            "model": "host_llm",
'''
if old not in text:
    raise SystemExit("Could not find parse-script response model field.")

text = text.replace(old, new, 1)

init_file.write_text(text, encoding="utf-8")
print("Updated parse-script route: host LLM only, no host model exposure.")
