from pathlib import Path

test_file = Path("tests/test_sqlite_render_jobs.py")
content = test_file.read_text(encoding="utf-8")

old_line = '    assert success["videoUrl"] == "data:video/mp4;base64,abc"\n'
new_lines = (
    '    assert success["videoUrl"] is None\n'
    '    assert success["videoRef"]["id"] == "remote-video"\n'
    '    assert success["videoRef"]["storage"] == "not_persisted"\n'
    '    assert success["videoRef"]["reason"] == "large_video_data_url"\n'
)

if old_line not in content:
    raise SystemExit("Old videoUrl assertion line was not found.")

content = content.replace(old_line, new_lines, 1)

# Remove the now-stale exact dict assertion if it is still present.
content = content.replace(
    '    assert success["videoRef"] == {"id": "remote-video"}\n',
    "",
    1,
)

test_file.write_text(content, encoding="utf-8")
print("Updated stale render-job assertion.")
