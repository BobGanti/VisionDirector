from pathlib import Path

# 1) Public bundle test: vault must be absent, not renamed.
host_test = Path("tests/test_host_managed_credentials.py")
text = host_test.read_text(encoding="utf-8")

old_line = '    assert "Host Provider Credentials" in body\n'
new_lines = (
    '    assert "Host Provider Credentials" not in body\n'
    '    assert "Paste Google API key" not in body\n'
    '    assert "Paste OpenAI API key" not in body\n'
    '    assert "Delete Google Key" not in body\n'
    '    assert "Delete OpenAI Key" not in body\n'
    '    assert "Update Keys" not in body\n'
)

if old_line not in text:
    raise SystemExit('Could not find old "Host Provider Credentials" assertion.')

text = text.replace(old_line, new_lines, 1)
host_test.write_text(text, encoding="utf-8")
print("Updated host-managed credentials bundle assertion.")


# 2) Execution test: SCRIPT_PARSER must use host LLM, not model override.
exec_test = Path("tests/test_model_router_execution.py")
text = exec_test.read_text(encoding="utf-8")

text = text.replace(
    "def test_parse_script_uses_current_effective_script_parser_model(tmp_path):",
    "def test_parse_script_uses_host_provided_script_parser_llm(tmp_path):",
    1,
)

old_assert = '    assert fake_client.models.calls[-1]["model"] == "current-script-model"\n'
new_assert = '    assert fake_client.models.calls[-1]["model"] == "host-profile-fallback-model"\n'

if old_assert not in text:
    raise SystemExit("Could not find old current-script-model assertion.")

text = text.replace(old_assert, new_assert, 1)
exec_test.write_text(text, encoding="utf-8")
print("Updated parse-script execution assertion for host-owned LLM.")
