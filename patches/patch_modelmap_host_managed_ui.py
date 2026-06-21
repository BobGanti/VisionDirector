from pathlib import Path

path = Path("components/ModelMap.tsx")
text = path.read_text(encoding="utf-8")

# 1) Track host-managed credential mode from backend status.
old = '''  const [credStatus, setCredStatus] = useState<{ google: boolean; openai: boolean }>({
    google: false,
    openai: false,
  });
'''
new = '''  const [credStatus, setCredStatus] = useState<{ google: boolean; openai: boolean; hostManaged: boolean }>({
    google: false,
    openai: false,
    hostManaged: false,
  });
'''
if old not in text:
    raise SystemExit("Could not find credStatus state block.")
text = text.replace(old, new, 1)

old = '''      const s = data?.status || {};
      setCredStatus({ google: !!s.google, openai: !!s.openai });
'''
new = '''      const s = data?.status || {};
      setCredStatus({
        google: !!s.google,
        openai: !!s.openai,
        hostManaged: !!data?.hostManaged,
      });
'''
if old not in text:
    raise SystemExit("Could not find refreshCredStatus assignment.")
text = text.replace(old, new, 1)

# 2) Make the model map explicit: only text LLM tasks are host-LLM tasks.
old = '''    const effectiveModel = (supplier: Supplier, key: string): string => {
      const s = registry[supplier];
      const ov = safeTrim(s?.drafts?.[key] ?? "");
      return ov || safeTrim(s?.defaults?.[key] ?? "");
    };
'''
new = '''    const effectiveModel = (supplier: Supplier, key: string): string => {
      const s = registry[supplier];
      const ov = safeTrim(s?.drafts?.[key] ?? "");
      return ov || safeTrim(s?.defaults?.[key] ?? "");
    };

    const hostLlmKeys = new Set(["SCRIPT_PARSER", "AUTO_NARRATOR"]);

    const displayModel = (supplier: Supplier, key: string): string => {
      const model = effectiveModel(supplier, key);
      if (hostLlmKeys.has(key)) {
        return model ? `Host LLM: ${model}` : "Host LLM not configured";
      }
      return model || "Not configured — specialist capability required";
    };

    const capabilityContext = (key: string): string => {
      return hostLlmKeys.has(key)
        ? `Host LLM capability key: ${key}`
        : `Specialist capability key: ${key}`;
    };
'''
if old not in text:
    raise SystemExit("Could not find mapData effectiveModel helper.")
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
            f'model: effectiveModel("{supplier}", "{key}") || "—",',
            f'model: displayModel("{supplier}", "{key}"),',
        )
        text = text.replace(
            f'context: "Agency key: {key}",',
            f'context: capabilityContext("{key}"),',
        )

# 3) Replace host-managed vault copy. Keep old handler code for dev fallback, but hide the UI when host-managed.
text = text.replace(
    '<p className="text-xl font-bold text-white uppercase tracking-tight">API Interface Credentials</p>',
    '<p className="text-xl font-bold text-white uppercase tracking-tight">Host Provider Status</p>',
    1,
)
text = text.replace(
    'Paste your keys to use this deployment. Keys are encrypted and stored in the instance database. You can delete them any time.',
    'Credentials are managed by the SyntaxMatrix host. This plugin does not accept, expose, or delete browser API keys in host-managed mode.',
    1,
)
text = text.replace('GOOGLE: {credStatus.google ? "SAVED" : "NOT SAVED"}', 'GOOGLE: {credStatus.google ? "HOST READY" : "HOST MISSING"}')
text = text.replace('OPENAI: {credStatus.openai ? "SAVED" : "NOT SAVED"}', 'OPENAI: {credStatus.openai ? "HOST READY" : "HOST MISSING"}')

start_marker = '''              <div className="flex flex-col gap-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
'''
start = text.find(start_marker)
if start < 0:
    raise SystemExit("Could not find vault controls start.")

end_marker = '''                <p className="text-[9px] text-zinc-600 uppercase font-bold tracking-widest">Paste keys only. No labels. No quotes.</p>
              </div>
'''
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("Could not find vault controls end.")
end += len(end_marker)

replacement = '''              {credStatus.hostManaged ? (
                <div className="rounded-3xl border border-emerald-500/15 bg-emerald-500/5 p-6">
                  <p className="text-[10px] font-black uppercase tracking-[0.35em] text-emerald-300 mb-3">
                    Host-managed credentials
                  </p>
                  <p className="text-sm text-zinc-300 leading-6">
                    API clients and secrets are supplied by the SyntaxMatrix host. VisionDirector receives provider availability only;
                    it does not render key-entry fields, store browser API keys, or allow key deletion from the Studio panel.
                  </p>
                </div>
              ) : (
                <div className="rounded-3xl border border-amber-500/15 bg-amber-500/5 p-6">
                  <p className="text-[10px] font-black uppercase tracking-[0.35em] text-amber-300 mb-3">
                    Local development fallback
                  </p>
                  <p className="text-sm text-zinc-300 leading-6">
                    This deployment is not reporting host-managed credentials. Configure provider clients in the SyntaxMatrix host before using Studio generation features.
                  </p>
                </div>
              )}
'''
text = text[:start] + replacement + text[end:]

path.write_text(text, encoding="utf-8")
print("Patched ModelMap.tsx: host-managed vault is read-only and model map separates host LLM from specialist capability tasks.")
