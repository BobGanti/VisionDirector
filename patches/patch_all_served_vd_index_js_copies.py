from pathlib import Path
import re

root = Path("..").resolve()
skip_parts = {".git", "venv", ".venv", "node_modules", ".pytest_cache", "__pycache__", "patches"}

candidates = []
for path in root.rglob("index.js"):
    if any(part in skip_parts for part in path.parts):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    if "Paste Google API key" in text or "Delete Google Key" in text or "Agency key: SCRIPT_PARSER" in text:
        candidates.append(path)

if not candidates:
    raise SystemExit("No VisionDirector index.js copies with old Studio strings were found.")

def patch_text(text: str) -> tuple[str, bool]:
    original = text

    text = re.sub(
        r'const \[credStatus, setCredStatus\] = useState\(\{\s*google: false,\s*openai: false\s*\}\);',
        'const [credStatus, setCredStatus] = useState({\n    google: false,\n    openai: false,\n    hostManaged: false\n  });',
        text,
        count=1,
    )

    text = text.replace(
        '''      const s = data?.status || {};
      setCredStatus({ google: !!s.google, openai: !!s.openai });''',
        '''      const s = data?.status || {};
      setCredStatus({
        google: !!s.google,
        openai: !!s.openai,
        hostManaged: !!data?.hostManaged
      });''',
        1,
    )

    if "const hostLlmKeys" not in text:
        text = text.replace(
            '''    const effectiveModel = (supplier, key) => {
      const s = registry[supplier];
      const ov = safeTrim(s?.drafts?.[key] ?? "");
      return ov || safeTrim(s?.defaults?.[key] ?? "");
    };''',
            '''    const effectiveModel = (supplier, key) => {
      const s = registry[supplier];
      const ov = safeTrim(s?.drafts?.[key] ?? "");
      return ov || safeTrim(s?.defaults?.[key] ?? "");
    };
    const hostLlmKeys = /* @__PURE__ */ new Set(["SCRIPT_PARSER", "AUTO_NARRATOR"]);
    const displayModel = (supplier, key) => {
      const model = effectiveModel(supplier, key);
      if (hostLlmKeys.has(key)) {
        return model ? `Host LLM: ${model}` : "Host LLM not configured";
      }
      return model || "Not configured — specialist capability required";
    };
    const capabilityContext = (key) => hostLlmKeys.has(key) ? `Host LLM capability key: ${key}` : `Specialist capability key: ${key}`;''',
            1,
        )

    for supplier in ("google", "openai"):
        for key in ("SCRIPT_PARSER", "DICTATION", "VOICE_ANALYZER", "AUTO_NARRATOR", "IMAGE_GEN", "VIDEO_GEN", "TTS_PREVIEW"):
            text = text.replace(
                f'model: effectiveModel("{supplier}", "{key}") || "\\\\u2014",',
                f'model: displayModel("{supplier}", "{key}"),',
            )
            text = text.replace(
                f'model: effectiveModel("{supplier}", "{key}") || "\\u2014",',
                f'model: displayModel("{supplier}", "{key}"),',
            )
            text = text.replace(
                f'model: effectiveModel("{supplier}", "{key}") || "—",',
                f'model: displayModel("{supplier}", "{key}"),',
            )
            text = text.replace(
                f'context: "Agency key: {key}",',
                f'context: capabilityContext("{key}"),',
            )

    text = text.replace(
        "Paste your keys to use this deployment. Keys are encrypted and stored in the instance database. You can delete them any time.",
        "Credentials are managed by the SyntaxMatrix host. This plugin does not accept, expose, or delete browser API keys in host-managed mode.",
    )

    # Replace the visible key-entry/delete block.
    marker_start = '        /* @__PURE__ */ jsxs3("div", { className: "flex flex-col gap-4", children: ['
    marker_end = '          /* @__PURE__ */ jsx3("p", { className: "text-[9px] text-zinc-600 uppercasefont-bold tracking-widest", children: "Paste keys only. No labels. No quotes." })\n        ] })'

    cred_idx = text.find("credMsg ?")
    start = text.find(marker_start, cred_idx if cred_idx >= 0 else 0)
    end = text.find(marker_end, start)

    if start >= 0 and end >= 0:
        end += len(marker_end)
        replacement = '''        credStatus.hostManaged ? /* @__PURE__ */ jsx3("div", {
          className: "rounded-3xl border border-emerald-500/15 bg-emerald-500/5 p-6",
          children: /* @__PURE__ */ jsxs3("div", { children: [
            /* @__PURE__ */ jsx3("p", {
              className: "text-[10px] font-black uppercase tracking-[0.35em] text-emerald-300 mb-3",
              children: "Host-managed credentials"
            }),
            /* @__PURE__ */ jsx3("p", {
              className: "text-sm text-zinc-300 leading-6",
              children: "API clients and secrets are supplied by the SyntaxMatrix host. VisionDirector receives provider availability only; it does not render key-entry fields, store browser API keys, or allow key deletion from the Studio panel."
            })
          ] })
        }) : /* @__PURE__ */ jsx3("div", {
          className: "rounded-3xl border border-amber-500/15 bg-amber-500/5 p-6",
          children: /* @__PURE__ */ jsxs3("div", { children: [
            /* @__PURE__ */ jsx3("p", {
              className: "text-[10px] font-black uppercase tracking-[0.35em] text-amber-300 mb-3",
              children: "Local development fallback"
            }),
            /* @__PURE__ */ jsx3("p", {
              className: "text-sm text-zinc-300 leading-6",
              children: "This deployment is not reporting host-managed credentials. Configure provider clients in the SyntaxMatrix host before using Studio generation features."
            })
          ] })
        })'''
        text = text[:start] + replacement + text[end:]

    return text, text != original

changed = []
for path in candidates:
    before = path.read_text(encoding="utf-8")
    after, did_change = patch_text(before)
    if did_change:
        path.write_text(after, encoding="utf-8")
        changed.append(path)

print("Patched files:")
for path in changed:
    text = path.read_text(encoding="utf-8")
    print(f"- {path}")
    print(f"  Paste Google API key: {text.count('Paste Google API key')}")
    print(f"  Delete Google Key: {text.count('Delete Google Key')}")
    print(f"  Agency key: {text.count('Agency key')}")
    print(f"  Host-managed credentials: {text.count('Host-managed credentials')}")
    print(f"  Specialist capability key: {text.count('Specialist capability key')}")
    print(f"  Host LLM:: {text.count('Host LLM:')}")

if not changed:
    raise SystemExit("Found old candidates, but no file changed.")
