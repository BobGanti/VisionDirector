from pathlib import Path

changed = []

# 1) Remove the source TSX vault block.
tsx = Path("components/ModelMap.tsx")
if tsx.exists():
    text = tsx.read_text(encoding="utf-8")
    start = text.find("        {/* Secure Vault Section */}")
    end_marker = "        {/* End Secure Vault */}"
    end = text.find(end_marker, start)

    if start >= 0 and end >= 0:
        end += len(end_marker)
        # Also remove the spacer immediately after the vault if present.
        after = text[end:]
        after = after.replace("\n\n        <br></br>\n", "\n", 1)
        text = text[:start] + after
        tsx.write_text(text, encoding="utf-8")
        changed.append(tsx)
    elif "Paste Google API key" in text or "Delete Google Key" in text:
        raise SystemExit("ModelMap.tsx still contains vault strings, but the vault block markers were not found.")

# 2) Remove the served bundled vault block from every active index.js copy.
root = Path("..").resolve()
skip_parts = {".git", "venv", ".venv", "node_modules", ".pytest_cache", "__pycache__", "patches"}

for js in root.rglob("index.js"):
    if any(part in skip_parts for part in js.parts):
        continue

    try:
        text = js.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    if "Paste Google API key" not in text and "Delete Google Key" not in text:
        continue

    start = text.find('    /* @__PURE__ */ jsx3("div", { id: "vault"')
    if start < 0:
        start = text.find('    /* @__PURE__ */ jsxs3("div", { id: "vault"')

    br = text.find('    /* @__PURE__ */ jsx3("br", {}),', start)

    if start < 0 or br < 0:
        raise SystemExit(f"Could not safely locate served vault block in {js}")

    end = br + len('    /* @__PURE__ */ jsx3("br", {}),\n')
    text = text[:start] + text[end:]

    js.write_text(text, encoding="utf-8")
    changed.append(js)

print("Removed Studio key-vault UI from:")
for path in changed:
    print(f"- {path}")

# 3) Verify no active served/source file still exposes old vault UI strings.
bad = []
for path in [Path("components/ModelMap.tsx"), *root.rglob("index.js")]:
    if any(part in skip_parts for part in path.parts):
        continue
    if not path.exists() or not path.is_file():
        continue

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    old_count = (
        text.count("Paste Google API key")
        + text.count("Paste OpenAI API key")
        + text.count("Delete Google Key")
        + text.count("Delete OpenAI Key")
        + text.count("Update Keys")
    )
    if old_count:
        bad.append((path, old_count))

if bad:
    for path, count in bad:
        print(f"STILL HAS OLD VAULT STRINGS: {path} count={count}")
    raise SystemExit("Old vault UI strings remain.")

print("Verified: active Studio files no longer expose key-vault UI strings.")
