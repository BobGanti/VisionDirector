from pathlib import Path

path = Path("src/smx_visiondirector/admin_dashboard.py")
text = path.read_text(encoding="utf-8")

old = '''            <a href="/visiondirector/admin#models">Models</a>
            <a href="/visiondirector/admin#analytics">Analytics</a>
          </nav>
'''

new = '''            <a href="/visiondirector/admin#models">Models</a>
            <a href="/visiondirector/admin#analytics">Analytics</a>
            <a class="smx-vd-logout-link" href="/visiondirector/admin/logout">Logout</a>
          </nav>
'''

if new in text:
    print("Mobile logout link already present.")
elif old not in text:
    raise SystemExit("Could not find exact mobile menu Analytics block.")
else:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("Added Logout link to mobile admin menu.")

