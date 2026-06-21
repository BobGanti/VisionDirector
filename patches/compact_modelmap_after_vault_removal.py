from pathlib import Path

changed = []

# 1) Source TSX spacing.
tsx = Path("components/ModelMap.tsx")
if tsx.exists():
    text = tsx.read_text(encoding="utf-8")
    original = text

    text = text.replace(
        'className="fixed inset-0 z-[300] bg-black/95 backdrop-blur-2xl flex justify-center p-4 lg:p-12 overflow-y-auto items-start py-12 lg:py-24"',
        'className="fixed inset-0 z-[300] bg-black/95 backdrop-blur-2xl flex justify-center p-4 lg:p-8 overflow-y-auto items-start py-6 lg:py-8"',
        1,
    )
    text = text.replace(
        'className="w-full max-w-6xl bg-[#0a0a0c] border border-white/10 rounded-[2rem] shadow-2xl p-8 lg:p-12 relative overflow-visible"',
        'className="w-full max-w-6xl bg-[#0a0a0c] border border-white/10 rounded-[2rem] shadow-2xl p-6 lg:p-8 relative overflow-visible"',
        1,
    )
    text = text.replace(
        'className="relative z-10 flex justify-end"',
        'className="relative z-10 flex justify-end mb-2"',
        1,
    )
    text = text.replace(
        'className="flex justify-between items-start mb-12 my-16"',
        'className="flex justify-between items-start mb-8 mt-2"',
        1,
    )

    if text != original:
        tsx.write_text(text, encoding="utf-8")
        changed.append(tsx)

# 2) Served bundle spacing.
root = Path("..").resolve()
skip_parts = {".git", "venv", ".venv", "node_modules", ".pytest_cache", "__pycache__", "patches"}

for js in root.rglob("index.js"):
    if any(part in skip_parts for part in js.parts):
        continue

    try:
        text = js.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    original = text

    text = text.replace(
        'className: "fixed inset-0 z-[300] bg-black/95 backdrop-blur-2xl flex justify-center p-4 lg:p-12 overflow-y-auto items-start py-12 lg:py-24"',
        'className: "fixed inset-0 z-[300] bg-black/95 backdrop-blur-2xl flex justify-center p-4 lg:p-8 overflow-y-auto items-start py-6 lg:py-8"',
        1,
    )
    text = text.replace(
        'className: "w-full max-w-6xl bg-[#0a0a0c] border border-white/10 rounded-[2rem] shadow-2xl p-8 lg:p-12 relative overflow-visible"',
        'className: "w-full max-w-6xl bg-[#0a0a0c] border border-white/10 rounded-[2rem] shadow-2xl p-6 lg:p-8 relative overflow-visible"',
        1,
    )
    text = text.replace(
        'className: "relative z-10 flex justify-end"',
        'className: "relative z-10 flex justify-end mb-2"',
        1,
    )
    text = text.replace(
        'className: "flex justify-between items-start mb-12 my-16"',
        'className: "flex justify-between items-start mb-8 mt-2"',
        1,
    )

    if text != original:
        js.write_text(text, encoding="utf-8")
        changed.append(js)

print("Compacted Studio model-map spacing in:")
for path in changed:
    print(f"- {path}")

if not changed:
    raise SystemExit("No spacing anchors changed. Need to inspect current ModelMap/index.js spacing.")

