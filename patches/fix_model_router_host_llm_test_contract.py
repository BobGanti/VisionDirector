from pathlib import Path

path = Path("tests/test_model_router.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "def test_model_router_resolves_override_default_then_host_profile():",
    "def test_model_router_resolves_host_llm_then_specialist_override_default():",
    1,
)

old = '''    assert router.resolve("google", "SCRIPT_PARSER").model == "default-script-model"
    assert router.resolve("google", "SCRIPT_PARSER").source == "default"
'''
new = '''    assert router.resolve("google", "SCRIPT_PARSER").model == "host-fallback-model"
    assert router.resolve("google", "SCRIPT_PARSER").source == "host_profile"
'''

if old not in text:
    raise SystemExit("Could not find old SCRIPT_PARSER assertions.")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Updated model router test: LLM tasks now resolve from host profile only.")
