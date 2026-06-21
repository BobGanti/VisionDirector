from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

broken = '''"<form method='post' onsubmit="return confirm('Delete this token event? This cannot be undone.');" action='/visiondirector/admin/usage-events/"'''

fixed = ''''<form method="post" onsubmit="return confirm(&quot;Delete this token event? This cannot be undone.&quot;);" action="/visiondirector/admin/usage-events/''''

if broken not in text:
    raise SystemExit("Could not find broken delete confirmation string.")

text = text.replace(broken, fixed, 1)
path.write_text(text, encoding="utf-8")
print("Fixed token-event delete confirmation string quoting.")
