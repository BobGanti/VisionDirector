import React, { useEffect, useMemo, useRef, useState } from "react";
import type { ModelMapping } from "../types";
import { refreshRuntimeKey, clearRuntimeKey, purgeLegacyLocalStorageKeys } from "../services/runtimeKeys";

import {
  fetchModelOverrides,
  resetModelOverrides,
  saveModelOverrides,
  type OverridesResponse,
  type Supplier,
} from "../services/modelOverrides";

type SupplierRegistryState = {
  keys: string[];
  defaults: Record<string, string>;
  drafts: Record<string, string>; // override values (empty string => use default)
  isLoading: boolean;
  isSaving: boolean;
  notice: string | null;
  error: string | null;
};

function safeTrim(v: any): string {
  return typeof v === "string" ? v.trim() : "";
}

function buildDrafts(keys: string[], overrides: Record<string, string>): Record<string, string> {
  const d: Record<string, string> = {};
  for (const k of keys) d[k] = safeTrim(overrides?.[k] ?? "");
  return d;
}

export const ModelMap: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  // -----------------------------
  // Model registry overrides (SQLite persisted; no localStorage)
  // -----------------------------

  const makeEmptyRegistryState = (): SupplierRegistryState => ({
    keys: [],
    defaults: {},
    drafts: {},
    isLoading: true,
    isSaving: false,
    notice: null,
    error: null,
  });

  const [registry, setRegistry] = useState<Record<Supplier, SupplierRegistryState>>(() => ({
    google: makeEmptyRegistryState(),
    openai: makeEmptyRegistryState(),
  }));

  const setSupplierState = (supplier: Supplier, patch: Partial<SupplierRegistryState>) => {
    setRegistry((prev) => ({
      ...prev,
      [supplier]: { ...prev[supplier], ...patch },
    }));
  };

  const loadSupplier = async (supplier: Supplier) => {
    setSupplierState(supplier, { isLoading: true, error: null, notice: null });
    try {
      const resp: OverridesResponse = await fetchModelOverrides(supplier);
      setSupplierState(supplier, {
        keys: resp.keys || [],
        defaults: resp.defaults || {},
        drafts: buildDrafts(resp.keys || [], resp.overrides || {}),
        isLoading: false,
      });
    } catch (e: any) {
      setSupplierState(supplier, {
        isLoading: false,
        error: e?.message || String(e || "MODEL_OVERRIDES_LOAD_FAILED"),
      });
    }
  };

  const saveSupplier = async (supplier: Supplier) => {
    const current = registry[supplier];
    setSupplierState(supplier, { isSaving: true, error: null, notice: null });
    try {
      const resp: OverridesResponse = await saveModelOverrides(supplier, current.drafts || {});
      setSupplierState(supplier, {
        keys: resp.keys || current.keys,
        defaults: resp.defaults || current.defaults,
        drafts: buildDrafts(resp.keys || current.keys, resp.overrides || {}),
        isSaving: false,
        notice: "Saved model overrides to SQLite.",
      });
      setTimeout(() => setSupplierState(supplier, { notice: null }), 2500);
    } catch (e: any) {
      setSupplierState(supplier, {
        isSaving: false,
        error: e?.message || String(e || "MODEL_OVERRIDES_SAVE_FAILED"),
      });
    }
  };

  const resetSupplier = async (supplier: Supplier) => {
    setSupplierState(supplier, { isSaving: true, error: null, notice: null });
    try {
      const resp: OverridesResponse = await resetModelOverrides(supplier);
      setSupplierState(supplier, {
        keys: resp.keys || [],
        defaults: resp.defaults || {},
        drafts: buildDrafts(resp.keys || [], resp.overrides || {}),
        isSaving: false,
        notice: "Reset to defaults.",
      });
      setTimeout(() => setSupplierState(supplier, { notice: null }), 2500);
    } catch (e: any) {
      setSupplierState(supplier, {
        isSaving: false,
        error: e?.message || String(e || "MODEL_OVERRIDES_RESET_FAILED"),
      });
    }
  };

  // Branding logo (stored locally; Studio header reads it)

  useEffect(() => {
    loadSupplier("google");
    loadSupplier("openai");
    purgeLegacyLocalStorageKeys();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Branding logo (stored locally; Studio header reads it)
  const LOGO_STORAGE_KEY = "vd_brand_logo_v1";
  const logoInputRef = useRef<HTMLInputElement>(null);

  const [brandLogo, setBrandLogo] = useState<string>(() => {
    try {
      return localStorage.getItem(LOGO_STORAGE_KEY) || "";
    } catch {
      return "";
    }
  });

  const fileToDataUrl = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error || new Error("READ_FAILED"));
      reader.readAsDataURL(file);
    });

  const broadcastLogoUpdate = () => {
    window.dispatchEvent(new Event("vd-logo-updated"));
  };

  const handleLogoPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      e.target.value = "";
      return;
    }

    try {
      const dataUrl = await fileToDataUrl(file);
      setBrandLogo(dataUrl);
      try {
        localStorage.setItem(LOGO_STORAGE_KEY, dataUrl);
      } catch {
        // ignore
      }
      broadcastLogoUpdate();
    } finally {
      // allow picking the same file again
      e.target.value = "";
    }
  };

  const clearLogo = () => {
    setBrandLogo("");
    try {
      localStorage.removeItem(LOGO_STORAGE_KEY);
    } catch {
      // ignore
    }
    broadcastLogoUpdate();
  };

  // -----------------------------
  // Blueprint map MUST match the table (effective model = override OR default)
  // -----------------------------
  const mapData: ModelMapping[] = useMemo(() => {
    const effectiveModel = (supplier: Supplier, key: string): string => {
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

    return [
      // Google
      {
        feature: "Google — Script Parser",
        model: displayModel("google", "SCRIPT_PARSER"),
        role: "Prompt → structured script",
        context: capabilityContext("SCRIPT_PARSER"),
        file: "shared/model_registry.json",
        method: "SCRIPT_PARSER",
      },
      {
        feature: "Google — Dictation",
        model: displayModel("google", "DICTATION"),
        role: "Audio → text",
        context: capabilityContext("DICTATION"),
        file: "shared/model_registry.json",
        method: "DICTATION",
      },
      {
        feature: "Google — Voice Analyser",
        model: displayModel("google", "VOICE_ANALYZER"),
        role: "Voice traits inference",
        context: capabilityContext("VOICE_ANALYZER"),
        file: "shared/model_registry.json",
        method: "VOICE_ANALYZER",
      },
      {
        feature: "Google — Auto Narrator",
        model: displayModel("google", "AUTO_NARRATOR"),
        role: "Narration generation",
        context: capabilityContext("AUTO_NARRATOR"),
        file: "shared/model_registry.json",
        method: "AUTO_NARRATOR",
      },
      {
        feature: "Google — Image Gen",
        model: displayModel("google", "IMAGE_GEN"),
        role: "Text/image → image",
        context: capabilityContext("IMAGE_GEN"),
        file: "shared/model_registry.json",
        method: "IMAGE_GEN",
      },
      {
        feature: "Google — Video Gen",
        model: displayModel("google", "VIDEO_GEN"),
        role: "Text/image → video",
        context: capabilityContext("VIDEO_GEN"),
        file: "shared/model_registry.json",
        method: "VIDEO_GEN",
      },
      {
        feature: "Google — TTS Preview",
        model: displayModel("google", "TTS_PREVIEW"),
        role: "Voice preview",
        context: capabilityContext("TTS_PREVIEW"),
        file: "shared/model_registry.json",
        method: "TTS_PREVIEW",
      },

      // OpenAI (if/when wired)
      {
        feature: "OpenAI — Script Parser",
        model: displayModel("openai", "SCRIPT_PARSER"),
        role: "Prompt → structured script",
        context: capabilityContext("SCRIPT_PARSER"),
        file: "shared/model_registry.json",
        method: "SCRIPT_PARSER",
      },
      {
        feature: "OpenAI — Dictation",
        model: displayModel("openai", "DICTATION"),
        role: "Audio → text",
        context: capabilityContext("DICTATION"),
        file: "shared/model_registry.json",
        method: "DICTATION",
      },
      {
        feature: "OpenAI — Voice Analyser",
        model: displayModel("openai", "VOICE_ANALYZER"),
        role: "Voice traits inference",
        context: capabilityContext("VOICE_ANALYZER"),
        file: "shared/model_registry.json",
        method: "VOICE_ANALYZER",
      },
      {
        feature: "OpenAI — Auto Narrator",
        model: displayModel("openai", "AUTO_NARRATOR"),
        role: "Narration generation",
        context: capabilityContext("AUTO_NARRATOR"),
        file: "shared/model_registry.json",
        method: "AUTO_NARRATOR",
      },
      {
        feature: "OpenAI — Image Gen",
        model: displayModel("openai", "IMAGE_GEN"),
        role: "Text/image → image",
        context: capabilityContext("IMAGE_GEN"),
        file: "shared/model_registry.json",
        method: "IMAGE_GEN",
      },
      {
        feature: "OpenAI — Video Gen",
        model: displayModel("openai", "VIDEO_GEN"),
        role: "Text/image → video",
        context: capabilityContext("VIDEO_GEN"),
        file: "shared/model_registry.json",
        method: "VIDEO_GEN",
      },
      {
        feature: "OpenAI — TTS Preview",
        model: displayModel("openai", "TTS_PREVIEW"),
        role: "Voice preview",
        context: capabilityContext("TTS_PREVIEW"),
        file: "shared/model_registry.json",
        method: "TTS_PREVIEW",
      },
    ];
  }, [registry]);

  // -----------------------------
  // Secure Vault (encrypted in SQLite; no localStorage)
  // -----------------------------
  const [googleKey, setGoogleKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [isSaved, setIsSaved] = useState(false);

  const [credStatus, setCredStatus] = useState<{ google: boolean; openai: boolean; hostManaged: boolean }>({
    google: false,
    openai: false,
    hostManaged: false,
  });
  const [credMsg, setCredMsg] = useState<string | null>(null);

  const refreshCredStatus = async () => {
    try {
      const res = await fetch("/api/credentials/status", { method: "GET" });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.error || `${res.status} ${res.statusText}`);

      const s = data?.status || {};
      setCredStatus({
        google: !!s.google,
        openai: !!s.openai,
        hostManaged: !!data?.hostManaged,
      });
    } catch (e: any) {
      setCredMsg(`CREDENTIALS STATUS ERROR: ${String(e?.message || e)}`);
    }
  };

  useEffect(() => {
    refreshCredStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSaveKeys = async () => {
    setCredMsg(null);
    const g = googleKey.trim();
    const o = openaiKey.trim();
    await refreshRuntimeKey("google");

    if (!g && !o) {
      setCredMsg("Paste at least one key, then click Update Keys.");
      return;
    }

    try {
      if (g) {
        const res = await fetch("/api/credentials/google", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ apiKey: g }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(data?.error || `GOOGLE SAVE FAILED: ${res.status}`);
      }

      if (o) {
        const res = await fetch("/api/credentials/openai", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ apiKey: o }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(data?.error || `OPENAI SAVE FAILED: ${res.status}`);
      }

      setGoogleKey("");
      setOpenaiKey("");

      await refreshCredStatus();

      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2500);
      await refreshRuntimeKey("openai");

      setCredMsg("Keys saved (encrypted in SQLite).");
      setTimeout(() => setCredMsg(null), 4000);
    } catch (e: any) {
      setCredMsg(String(e?.message || e));
    }
  };

  const deleteGoogleKey = async () => {
    const ok = window.confirm("Delete saved Google API key?");
    if (!ok) return;

    setCredMsg(null);
    try {
      const res = await fetch("/api/credentials/google", { method: "DELETE" });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.error || `DELETE FAILED: ${res.status}`);

      await refreshCredStatus();
      setCredMsg("Google key deleted.");
      setTimeout(() => setCredMsg(null), 3000);

      clearRuntimeKey("google");
      purgeLegacyLocalStorageKeys();

    } catch (e: any) {
      setCredMsg(String(e?.message || e));
    }
  };

  const deleteOpenAIKey = async () => {
    const ok = window.confirm("Delete saved OpenAI API key?");
    if (!ok) return;

    setCredMsg(null);
    try {
      const res = await fetch("/api/credentials/openai", { method: "DELETE" });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.error || `DELETE FAILED: ${res.status}`);

      await refreshCredStatus();
      setCredMsg("OpenAI key deleted.");
      setTimeout(() => setCredMsg(null), 3000);
      clearRuntimeKey("openai");
      purgeLegacyLocalStorageKeys();

    } catch (e: any) {
      setCredMsg(String(e?.message || e));
    }
  };

  const RegistryPanel: React.FC<{ supplier: Supplier; title: string; accent: "emerald" | "violet" }> = ({
    supplier,
    title,
    accent,
  }) => {
    const s = registry[supplier];

    const effectiveFor = (k: string): string => {
      const ov = safeTrim(s.drafts?.[k] ?? "");
      if (ov) return ov;
      return safeTrim(s.defaults?.[k] ?? "");
    };

    const accentText500 = accent === "emerald" ? "text-emerald-500" : "text-violet-500";
    const accentBadgeBg =
      accent === "emerald"
        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
        : "bg-violet-500/10 border-violet-500/20 text-violet-400";
    const accentBtn =
      accent === "emerald"
        ? "bg-emerald-600/20 hover:bg-emerald-600/30 border-emerald-500/20 text-emerald-200"
        : "bg-violet-600/20 hover:bg-violet-600/30 border-violet-500/20 text-violet-200";
    const accentEffective = accent === "emerald" ? "text-emerald-300" : "text-violet-300";

    return (
      <div className="bg-white/[0.03] border border-white/5 rounded-3xl p-6 lg:p-8">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <p className={`text-[10px] font-black uppercase tracking-[0.4em] ${accentText500} mb-2`}>Model Registry</p>
            <h3 className="text-xl font-black text-white uppercase tracking-tight">{title}</h3>
            <p className="text-[10px] text-zinc-500 mt-2 uppercase font-medium">
              Overrides persist to SQLite. Leave override blank to use the default.
            </p>
          </div>

          <div className="flex flex-col items-end gap-2">
            {s.notice ? (
              <div className={`px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border ${accentBadgeBg}`}>
                <i className="fas fa-check mr-2"></i>
                {s.notice}
              </div>
            ) : null}
            {s.error ? (
              <div className="px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest bg-red-500/10 border border-red-500/20 text-red-400 max-w-[320px] break-words">
                <i className="fas fa-triangle-exclamation mr-2"></i>
                {s.error}
              </div>
            ) : null}
          </div>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-white/5 bg-black/30">
          <table className="min-w-full text-left">
            <thead className="bg-white/[0.03]">
              <tr>
                <th className="px-4 py-3 text-[9px] uppercase font-black tracking-widest text-zinc-500">Agency Key</th>
                <th className="px-4 py-3 text-[9px] uppercase font-black tracking-widest text-zinc-500">Default Model</th>
                <th className="px-4 py-3 text-[9px] uppercase font-black tracking-widest text-zinc-500">Override</th>
                <th className="px-4 py-3 text-[9px] uppercase font-black tracking-widest text-zinc-500">Effective</th>
              </tr>
            </thead>
            <tbody>
              {s.isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-xs text-zinc-500">
                    Loading registry…
                  </td>
                </tr>
              ) : (
                (s.keys || []).map((k) => (
                  <tr key={k} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3">
                      <code className="text-[11px] font-mono text-emerald-400 bg-emerald-500/5 px-2 py-1 rounded select-all">{k}</code>
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-[11px] font-mono text-zinc-300 select-all">{safeTrim(s.defaults?.[k] ?? "") || "—"}</code>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        value={s.drafts?.[k] ?? ""}
                        onChange={(e) => {
                          const v = e.target.value;
                          setSupplierState(supplier, { drafts: { ...(s.drafts || {}), [k]: v } });
                        }}
                        placeholder="(blank = default)"
                        className="w-full min-w-[220px] bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[11px] font-mono text-white focus:border-white/20 outline-none transition-all placeholder:text-zinc-700"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <code className={`text-[11px] font-mono ${accentEffective} select-all`}>{effectiveFor(k) || "—"}</code>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-5 flex flex-col md:flex-row gap-3 md:items-center md:justify-end">
          <button
            onClick={() => resetSupplier(supplier)}
            disabled={s.isLoading || s.isSaving}
            className="px-6 h-11 rounded-2xl font-black uppercase tracking-widest text-[10px] transition-all flex items-center justify-center gap-3 bg-white/5 hover:bg-white/10 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <i className="fas fa-rotate-left"></i>
            Reset to defaults
          </button>
          <button
            onClick={() => saveSupplier(supplier)}
            disabled={s.isLoading || s.isSaving}
            className={`px-6 h-11 rounded-2xl font-black uppercase tracking-widest text-[10px] transition-all flex items-center justify-center gap-3 border ${accentBtn} disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <i className={`fas ${s.isSaving ? "fa-spinner fa-spin" : "fa-floppy-disk"}`}></i>
            {s.isSaving ? "Saving…" : "Save model overrides"}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[300] bg-black/95 backdrop-blur-2xl flex justify-center p-4 lg:p-8 overflow-y-auto items-start py-6 lg:py-8">
      <div className="w-full max-w-6xl bg-[#0a0a0c] border border-white/10 rounded-[2rem] shadow-2xl p-6 lg:p-8 relative overflow-visible">
        <div
          className="absolute inset-0 opacity-5 pointer-events-none rounded-[2rem]"
          style={{
            backgroundImage: "radial-gradient(circle at 2px 2px, white 1px, transparent 0)",
            backgroundSize: "24px 24px",
          }}
        ></div>
        <div className="relative z-10 flex justify-end mb-2">
          <button
            onClick={onClose}
            className="my-4 w-12 h-12 bg-white/5 hover:bg-white/10 rounded-full flex items-center justify-center transition-all sticky top-0"
          >
            ✖
          </button>
        </div>



        <div className="relative z-10">
          <div className="flex justify-between items-start mb-8 mt-2">
            <div>
              <h2 className="text-[12px] font-black uppercase tracking-[0.5em] text-violet-500 mb-2">Model Blueprint</h2>
              <p className="text-3xl font-black uppercase tracking-tight text-white">Live Model Map</p>
              <p className="text-[11px] uppercase font-medium text-zinc-500 mt-2 max-w-2xl">
                This blueprint displays the current effective model per capability. Use the registry panels below to override defaults.
              </p>
            </div>

            <a
              href="https://ai.google.dev/gemini-api/docs/models/gemini"
              target="_blank"
              rel="noreferrer"
              className="hidden md:flex items-center gap-3 px-6 h-11 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 text-white transition-all text-[10px] font-black uppercase tracking-widest"
            >
              <i className="fas fa-book"></i>
              Google Model Docs
            </a>
          </div>

          <div className="overflow-x-auto rounded-3xl border border-white/10 bg-black/40 shadow-2xl">
            <table className="min-w-full text-left">
              <thead className="bg-white/[0.03]">
                <tr>
                  <th className="px-6 py-4 text-[9px] uppercase font-black tracking-widest text-zinc-500">Feature</th>
                  <th className="px-6 py-4 text-[9px] uppercase font-black tracking-widest text-zinc-500">Model</th>
                  <th className="px-6 py-4 text-[9px] uppercase font-black tracking-widest text-zinc-500">Role</th>
                  <th className="px-6 py-4 text-[9px] uppercase font-black tracking-widest text-zinc-500">Context</th>
                  <th className="px-6 py-4 text-[9px] uppercase font-black tracking-widest text-zinc-500">Registry File</th>
                  <th className="px-6 py-4 text-[9px] uppercase font-black tracking-widest text-zinc-500">Key</th>
                </tr>
              </thead>
              <tbody>
                {mapData.map((row, idx) => (
                  <tr key={idx} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="px-6 py-4 text-[11px] font-black text-white uppercase tracking-tight">{row.feature}</td>
                    <td className="px-6 py-4">
                      <code className="text-[11px] font-mono text-emerald-300 bg-emerald-500/5 px-2 py-1 rounded select-all">{row.model}</code>
                    </td>
                    <td className="px-6 py-4 text-[11px] text-zinc-400">{row.role}</td>
                    <td className="px-6 py-4 text-[11px] text-zinc-500">{row.context}</td>
                    <td className="px-6 py-4 text-[11px] text-zinc-600 font-mono select-all">{row.file}</td>
                    <td className="px-6 py-4">
                      <code className="text-[11px] font-mono text-violet-300 bg-violet-500/5 px-2 py-1 rounded select-all">{row.method}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-10">
            <RegistryPanel supplier="google" title="Google (Gemini)" accent="emerald" />
            <RegistryPanel supplier="openai" title="OpenAI" accent="violet" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ModelMap;
