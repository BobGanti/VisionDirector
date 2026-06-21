from __future__ import annotations

from pathlib import Path
from textwrap import dedent

init_file = Path("src/smx_visiondirector/__init__.py")
lines = init_file.read_text(encoding="utf-8").splitlines()

if any(line.strip() == "def _rewrite_runtime_js_urls(js: str) -> str:" for line in lines):
    print("_rewrite_runtime_js_urls helper already present.")
else:
    insert_at = None
    for i, line in enumerate(lines):
        if line == "    def _visiondirector_index_asset_path(filename: str) -> Path | None:":
            insert_at = i
            break

    if insert_at is None:
        raise SystemExit("Could not find correctly scoped _visiondirector_index_asset_path anchor.")

    helper_block = dedent(
        '''
        def _rewrite_runtime_js_urls(js: str) -> str:
            """
            Serve the browser bundle from the plugin namespace.

            The frontend bundle was originally authored with root-relative API calls.
            When hosted as a SyntaxMatrix plugin, those calls must stay under
            /visiondirector so the plugin never leaks routes into the host root.
            """
            replacements = {
                '"/api/': '"/visiondirector/api/',
                "'/api/": "'/visiondirector/api/",
                "`/api/": "`/visiondirector/api/",
                '"api/': '"/visiondirector/api/',
                "'api/": "'/visiondirector/api/",
                "`api/": "`/visiondirector/api/",
            }

            patched = js
            for old, new in replacements.items():
                patched = patched.replace(old, new)

            return patched


        def _rewrite_index_asset_urls(html: str) -> str:
            return (
                html.replace('src="/index.js"', 'src="/visiondirector/index.js"')
                .replace("src='/index.js'", "src='/visiondirector/index.js'")
                .replace('href="/index.css"', 'href="/visiondirector/index.css"')
                .replace("href='/index.css'", "href='/visiondirector/index.css'")
            )


        def _inject_safe_runtime(html: str, *, config, profile_registry) -> str:
            return html
        '''
    ).splitlines()

    helper_block = [("    " + line) if line.strip() else "" for line in helper_block]
    lines = lines[:insert_at] + helper_block + [""] + lines[insert_at:]

    init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Inserted missing index asset helper functions inside blueprint factory.")
