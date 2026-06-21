from __future__ import annotations

import ast
from pathlib import Path

p = Path("src/smx_visiondirector/__init__.py")
text = p.read_text(encoding="utf-8")
lines = text.splitlines()

print("FILE:", p)
print("TOTAL LINES:", len(lines))
print()

try:
    tree = ast.parse(text)
    print("AST PARSE: OK")
except SyntaxError as exc:
    print("AST PARSE: FAILED")
    print(exc)
    raise SystemExit(1)

print()
print("TOP-LEVEL FUNCTIONS:")
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        print(f"  line {node.lineno}: def {node.name}(...), ends line {node.end_lineno}")

print()
print("SETUP NAME SEARCH:")
for i, line in enumerate(lines, start=1):
    if "setup_visiondirector" in line:
        print(f"{i}: {line}")

print()
print("ADMIN LOGIN/LOGOUT SEARCH:")
for i, line in enumerate(lines, start=1):
    if "admin/login" in line or "admin/logout" in line or "_smx_visiondirector_admin_logout" in line:
        print(f"{i}: {line}")

print()
print("LINES 760-880:")
for i in range(760, min(881, len(lines) + 1)):
    print(f"{i}: {lines[i-1]}")
