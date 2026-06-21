from pathlib import Path

# 1) Host-managed bundle test: the vault must be removed, not renamed.
host_test = Path("tests/test_host_managed_credentials.py")
text = host_test.read_text(encoding="utf-8")

old = '''    assert "Host Provider Credentials" in body
    assert "Paste Google API key" not in body
    assert "Paste OpenAI API key" not in body
    assert "Delete Google Key" not in body
    assert "Delete OpenAI Key" not in body
'''

new = '''    assert "Paste Google API key" not in body
    assert "Paste OpenAI API key" not in body
    assert "Delete Google Key" not in body
    assert "Delete OpenAI Key" not in body
    assert "Update Keys" not in body
'''

if old not in text:
    raise SystemExit("Could not find old host-managed credential bundle assertions.")

text = text.replace(old, new, 1)
host_test.write_text(text, encoding="utf-8")
print("Updated host-managed credential bundle test: Studio key vault must be absent.")


# 2) Model router execution test: SCRIPT_PARSER must use host LLM, not model-map override.
router_test = Path("tests/test_model_router_execution.py")
text = router_test.read_text(encoding="utf-8")

text = text.replace(
    "def test_parse_script_uses_current_effective_script_parser_model(tmp_path):",
    "def test_parse_script_uses_host_provided_script_parser_llm(tmp_path):",
    1,
)

old = '''    update = client.post(
        "/visiondirector/api/model-overrides/google",
        json={
            "overrides": {
                "SCRIPT_PARSER": "current-script-model",
            }
        },
    )
    assert update.status_code == 200

    response = client.post(
'''

new = '''    # LLM tasks are host-owned. A SCRIPT_PARSER override must not replace
    # the host-provided LLM model.
    update = client.post(
        "/visiondirector/api/model-overrides/google",
        json={
            "overrides": {
                "SCRIPT_PARSER": "current-script-model",
            }
        },
    )
    assert update.status_code == 200

    response = client.post(
'''

if old not in text:
    raise SystemExit("Could not find SCRIPT_PARSER override setup block.")

text = text.replace(old, new, 1)

old = '''    assert fake_client.models.calls[-1]["model"] == "current-script-model"
'''

new = '''    assert fake_client.models.calls[-1]["model"] == "host-profile-fallback-model"
'''

if old not in text:
    raise SystemExit("Could not find old SCRIPT_PARSER model assertion.")

text = text.replace(old, new, 1)
router_test.write_text(text, encoding="utf-8")
print("Updated parse-script execution test: SCRIPT_PARSER uses host LLM.")
