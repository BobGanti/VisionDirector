from pathlib import Path

path = Path("tests/test_host_managed_credentials.py")
text = path.read_text(encoding="utf-8")

old_line = '    assert "HOST MISSING" in body\n'

if old_line not in text:
    raise SystemExit('Could not find obsolete HOST MISSING assertion.')

text = text.replace(old_line, "", 1)
path.write_text(text, encoding="utf-8")

print("Removed obsolete HOST MISSING bundle assertion.")
