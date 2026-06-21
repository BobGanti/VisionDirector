from pathlib import Path

p = Path("tests/test_model_router.py")
s = p.read_text(encoding="utf-8")

old = '''    assert payload["defaults"] == {"IMAGE_GEN": "new-image-model"}
    assert payload["overrides"] == {}
    assert payload["models"]["IMAGE_GEN"]["model"] == "new-image-model"
    assert "old-image-model" not in str(payload)
    assert "previous" not in str(payload).lower()
    assert "current" not in str(payload).lower()
'''

new = '''    assert payload["defaults"]["IMAGE_GEN"] == "new-image-model"
    assert payload["overrides"] == {}
    assert payload["models"]["IMAGE_GEN"]["model"] == "new-image-model"

    # The clean model map may include other known VisionDirector task keys,
    # but each key must show only its current effective model.
    assert "SCRIPT_PARSER" in payload["defaults"]
    assert payload["defaults"]["SCRIPT_PARSER"] == "host-fallback-model"

    # The retired/replaced model must no longer feature anywhere.
    assert "old-image-model" not in str(payload)
    assert "previous" not in str(payload).lower()
    assert "current" not in str(payload).lower()
'''

if old not in s:
    raise SystemExit("Could not find old assertion block in tests/test_model_router.py")

p.write_text(s.replace(old, new), encoding="utf-8")
print("fixed clean model map test expectation")
