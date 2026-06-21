from pathlib import Path

path = Path("index.js")
text = path.read_text(encoding="utf-8")

# 1) Served bundle: add hostManaged to credential status state.
old = '''  const [credStatus, setCredStatus] = useState({
    google: false,
    openai: false
  });
'''
new = '''  const [credStatus, setCredStatus] = useState({
    google: false,
    openai: false,
    hostManaged: false
  });
'''
if old not in text:
    raise SystemExit("Could not find index.js credStatus state block.")
text = text.replace(old, new, 1)

old = '''      const s = data?.status || {};
      setCredStatus({ google: !!s.google, openai: !!s.openai });
'''
new = '''      const s = data?.status || {};
      setCredStatus({
        google: !!s.google,
        openai: !!s.openai,
        hostManaged: !!data?.hostManaged
      });
'''
if old not in text:
    raise SystemExit("Could not find index.js refreshCredStatus assignment.")
text = text.replace(old, new, 1)

# 2) Served bundle: model map must distinguish host LLM tasks from specialist capability tasks.
old = '''    const effectiveModel = (supplier, key) => {
      const s = registry[supplier];
      const ov = safeTrim(s?.drafts?.[key] ?? "");
      return ov || safeTrim(s?.defaults?.[key] ?? "");
    };
'''
new = '''    const effectiveModel = (supplier, key) => {
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
    const capabilityContext = (key) => hostLlmKeys.has(key) ? `Host LLM capability key: ${key}` : `Specialist capability key: ${key}`;
'''
if old not in text:
    raise SystemExit("Could not find index.js mapData effectiveModel helper.")
text = text.replace(old, new, 1)

for supplier in ("google", "openai"):
    for key in (
        "SCRIPT_PARSER",
        "DICTATION",
        "VOICE_ANALYZER",
        "AUTO_NARRATOR",
        "IMAGE_GEN",
        "VIDEO_GEN",
        "TTS_PREVIEW",
    ):
        text = text.replace(
            f'model: effectiveModel("{supplier}", "{key}") || "\\u2014",',
            f'model: displayModel("{supplier}", "{key}"),',
        )
        text = text.replace(
            f'context: "Agency key: {key}",',
            f'context: capabilityContext("{key}"),',
        )

# 3) Served bundle: replace visible key-entry/delete UI with read-only host-managed provider panel.
start_marker = '''        /* @__PURE__ */ jsxs3("div", { className: "flex flex-col gap-4", children: [
'''
end_marker = '''          /* @__PURE__ */ jsx3("p", { className: "text-[9px] text-zinc-600 uppercasefont-bold tracking-widest", children: "Paste keys only. No labels. No quotes." })
        ] })
'''
start = text.find(start_marker)
if start < 0:
    raise SystemExit("Could not find index.js vault controls start marker.")
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("Could not find index.js vault controls end marker.")
end += len(end_marker)

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
        })
'''
text = text[:start] + replacement + text[end:]

path.write_text(text, encoding="utf-8")
print("Patched served index.js: host-managed vault is read-only and model map labels host LLM vs specialist capability tasks.")
