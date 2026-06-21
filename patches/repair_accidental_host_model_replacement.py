from pathlib import Path

# 1) Repair accidental credentials/status regression.
# The credentials status endpoint may report safe host model names, but never secrets.
init_file = Path("src/smx_visiondirector/__init__.py")
text = init_file.read_text(encoding="utf-8")

start = text.find("def _host_provider_status_payload():")
if start < 0:
    raise SystemExit("Could not find _host_provider_status_payload().")

end = text.find('@bp.get("/api/credentials/status")', start)
if end < 0:
    raise SystemExit("Could not find credentials/status route after _host_provider_status_payload().")

section = text[start:end]
old = '"model": "host_llm",'
new = '"model": model,'

if old not in section:
    raise SystemExit("Credentials status section does not contain the accidental host_llm replacement.")

section = section.replace(old, new, 1)
text = text[:start] + section + text[end:]
init_file.write_text(text, encoding="utf-8")
print("Repaired credentials/status provider model field.")


# 2) Fix obsolete test assertion.
# The vault panel is removed, so the public bundle should not be required to contain HOST READY.
test_file = Path("tests/test_host_managed_credentials.py")
text = test_file.read_text(encoding="utf-8")

old_line = '    assert "HOST READY" in body\n'
if old_line not in text:
    raise SystemExit('Could not find obsolete HOST READY assertion.')

text = text.replace(old_line, "", 1)
test_file.write_text(text, encoding="utf-8")
print("Removed obsolete HOST READY bundle assertion.")
