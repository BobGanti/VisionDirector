from __future__ import annotations

from pathlib import Path

init_file = Path("src/smx_visiondirector/__init__.py")
content = init_file.read_text(encoding="utf-8")

old = '''  if (data.audioUrl) {
    const audio = new Audio(data.audioUrl);
    await audio.play();
  }
'''

new = '''  const audioUrl = data.audioUrl;
  if (audioUrl) {
    const audio = new Audio(audioUrl);
    await audio.play();
  }
'''

if old not in content:
    if "new Audio(audioUrl)" in content:
        print("Runtime bridge already uses audioUrl variable.")
    else:
        raise SystemExit("Could not find data.audioUrl audio playback block.")
else:
    content = content.replace(old, new, 1)
    init_file.write_text(content, encoding="utf-8")
    print("Repaired runtime bridge to use audioUrl variable.")

