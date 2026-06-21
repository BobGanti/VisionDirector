from pathlib import Path

test_file = Path("tests/test_sqlite_render_jobs.py")
content = test_file.read_text(encoding="utf-8")

old = '''    success = store.get("job-2")
    assert success is not None
    assert success["status"] == "success"
    assert success["videoUrl"] == "data:video/mp4;base64,abc"
    assert success["videoRef"] == {"id": "remote-video"}
'''

new = '''    success = store.get("job-2")
    assert success is not None
    assert success["status"] == "success"
    assert success["videoUrl"] is None
    assert success["videoRef"]["id"] == "remote-video"
    assert success["videoRef"]["storage"] == "not_persisted"
    assert success["videoRef"]["reason"] == "large_video_data_url"
'''

if old not in content:
    raise SystemExit("Could not find old render job success assertions.")

content = content.replace(old, new, 1)
test_file.write_text(content, encoding="utf-8")

print("Updated old render-job test to match no-base64-persistence rule.")
