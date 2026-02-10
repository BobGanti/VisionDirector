import React, { useEffect, useMemo, useState } from "react";
import type { ModelMapping } from "../types";

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

  useEffect(() => {
    loadSupplier("google");
    loadSupplier("openai");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -----------------------------
  // Blueprint map MUST match the table (effective model = override OR default)
  // -----------------------------
  const mapData: ModelMapping[] = useMemo(() => {
    const effectiveModel = (supplier: Supplier, key: string): string => {
      const s = registry[supplier];
      const ov = safeTrim(s?.drafts?.[key] ?? "");
      return ov || safeTrim(s?.defaults?.[key] ?? "");
    };

    return [
      // Google
      {
        feature: "Google — Script Parser",
        model: effectiveModel("google", "SCRIPT_PARSER") || "—",
        role: "Prompt → structured script",
        context: "Agency key: SCRIPT_PARSER",
        file: "shared/model_registry.json",
        method: "SCRIPT_PARSER",
      },
      {
        feature: "Google — Dictation",
        model: effectiveModel("google", "DICTATION") || "—",
        role: "Audio → text",
        context: "Agency key: DICTATION",
        file: "shared/model_registry.json",
        method: "DICTATION",
      },
      {
        feature: "Google — Voice Analyser",
        model: effectiveModel("google", "VOICE_ANALYZER") || "—",
        role: "Voice traits inference",
        context: "Agency key: VOICE_ANALYZER",
        file: "shared/model_registry.json",
        method: "VOICE_ANALYZER",
      },
      {
        feature: "Google — Auto Narrator",
        model: effectiveModel("google", "AUTO_NARRATOR") || "—",
        role: "Narration generation",
        context: "Agency key: AUTO_NARRATOR",
        file: "shared/model_registry.json",
        method: "AUTO_NARRATOR",
      },
      {
        feature: "Google — Image Gen",
        model: effectiveModel("google", "IMAGE_GEN") || "—",
        role: "Text/image → image",
        context: "Agency key: IMAGE_GEN",
        file: "shared/model_registry.json",
        method: "IMAGE_GEN",
      },
      {
        feature: "Google — Video Gen",
        model: effectiveModel("google", "VIDEO_GEN") || "—",
        role: "Text/image → video",
        context: "Agency key: VIDEO_GEN",
        file: "shared/model_registry.json",
        method: "VIDEO_GEN",
      },
      {
        feature: "Google — TTS Preview",
        model: effectiveModel("google", "TTS_PREVIEW") || "—",
        role: "Text → speech",
        context: "Agency key: TTS_PREVIEW",
        file: "shared/model_registry.json",
        method: "TTS_PREVIEW",
      },

      // OpenAI
      {
        feature: "OpenAI — Script Parser",
        model: effectiveModel("openai", "SCRIPT_PARSER") || "—",
        role: "Prompt → structured script",
        context: "Agency key: SCRIPT_PARSER",
        file: "shared/model_registry.json",
        method: "SCRIPT_PARSER",
      },
      {
        feature: "OpenAI — Dictation",
        model: effectiveModel("openai", "DICTATION") || "—",
        role: "Audio → text",
        context: "Agency key: DICTATION",
        file: "shared/model_registry.json",
        method: "DICTATION",
      },
      {
        feature: "OpenAI — Voice Analyser",
        model: effectiveModel("openai", "VOICE_ANALYZER") || "—",
        role: "Voice traits inference",
        context: "Agency key: VOICE_ANALYZER",
        file: "shared/model_registry.json",
        method: "VOICE_ANALYZER",
      },
      {
        feature: "OpenAI — Auto Narrator",
        model: effectiveModel("openai", "AUTO_NARRATOR") || "—",
        role: "Narration generation",
        context: "Agency key: AUTO_NARRATOR",
        file: "shared/model_registry.json",
        method: "AUTO_NARRATOR",
      },
      {
        feature: "OpenAI — Image Gen",
        model: effectiveModel("openai", "IMAGE_GEN") || "—",
        role: "Text → image",
        context: "Agency key: IMAGE_GEN",
        file: "shared/model_registry.json",
        method: "IMAGE_GEN",
      },
      {
        feature: "OpenAI — Video Gen",
        model: effectiveModel("openai", "VIDEO_GEN") || "—",
        role: "Text/image → video",
        context: "Agency key: VIDEO_GEN",
        file: "shared/model_registry.json",
        method: "VIDEO_GEN",
      },
      {
        feature: "OpenAI — TTS Preview",
        model: effectiveModel("openai", "TTS_PREVIEW") || "—",
        role: "Text → speech",
        context: "Agency key: TTS_PREVIEW",
        file: "shared/model_registry.json",
        method: "TTS_PREVIEW",
      },
    ];
  }, [registry]);

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
    <div className="fixed inset-0 z-[300] bg-black/95 backdrop-blur-2xl flex justify-center p-4 lg:p-12 overflow-y-auto items-start py-12 lg:py-24">
      <div className="w-full max-w-6xl bg-[#0a0a0c] border border-white/10 rounded-[2rem] shadow-2xl p-8 lg:p-12 relative overflow-visible">
        <div
          className="absolute inset-0 opacity-5 pointer-events-none rounded-[2rem]"
          style={{
            backgroundImage: "radial-gradient(circle at 2px 2px, white 1px, transparent 0)",
            backgroundSize: "24px 24px",
          }}
        ></div>

        <div className="relative z-10">
          <div className="flex justify-between items-start mb-12">
            <div>
              <h2 className="text-[12px] font-black uppercase tracking-[0.5em] text-violet-500 mb-2">Architectural Map</h2>
              <h1 className="text-4xl lg:text-5xl font-black text-white uppercase tracking-tighter">Model Blueprint</h1>
              <div className="mt-4 flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-xl w-fit">
                <i className="fas fa-search text-emerald-400 text-xs"></i>
                <p className="text-[10px] text-emerald-400 uppercase tracking-widest font-black">
                  Search project for <span className="underline select-all">@MODEL_CALL_SITE</span> to find code points.
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="w-12 h-12 bg-white/5 hover:bg-white/10 rounded-full flex items-center justify-center transition-all sticky top-0"
            >
              <i className="fas fa-times"></i>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6 mb-12">
            {mapData.map((item, idx) => (
              <div
                key={idx}
                className="bg-white/[0.03] border border-white/5 p-6 rounded-2xl hover:border-violet-500/50 transition-all group"
              >
                <div className="flex items-center justify-between mb-4">
                  <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500 group-hover:text-violet-400">
                    {item.feature}
                  </span>
                  <div className="px-2 py-1 bg-violet-600/10 border border-violet-500/20 rounded text-[9px] font-bold text-violet-400">
                    NODE_{idx + 1}
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <p className="text-[9px] uppercase font-black text-zinc-600 mb-1">Model (effective)</p>
                    <code className="text-sm font-mono text-emerald-400 bg-emerald-500/5 px-2 py-1 rounded select-all block mb-2">
                      {item.model}
                    </code>
                  </div>

                  <div className="p-3 bg-black/40 rounded-xl border border-white/5">
                    <p className="text-[9px] uppercase font-black text-violet-500 mb-2">Source Reference</p>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <i className="fas fa-file-code text-[10px] text-zinc-600"></i>
                        <code className="text-[10px] text-zinc-400 font-mono">{item.file}</code>
                      </div>
                      <div className="flex items-center gap-2">
                        <i className="fas fa-terminal text-[10px] text-zinc-600"></i>
                        <code className="text-[10px] text-violet-400 font-mono">{item.method}</code>
                      </div>
                    </div>
                  </div>

                  <div>
                    <p className="text-[9px] uppercase font-black text-zinc-600 mb-1">Functional Use-Case</p>
                    <p className="text-xs text-zinc-400 leading-relaxed italic">"{item.context}"</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Model Editing Table (Registry Override Grid) */}
          <div className="mb-12">
            <div className="mb-6">
              <h3 className="text-[10px] font-black uppercase tracking-[0.4em] text-violet-500 mb-2">Registry Override Grid</h3>
              <p className="text-xl font-bold text-white uppercase tracking-tight">Model Editing Table</p>
              <p className="text-[10px] text-zinc-500 mt-1 uppercase font-medium">
                Two tables (Google + OpenAI) share the same agency keys. Overrides are stored in SQLite (no browser persistence).
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
              <RegistryPanel supplier="google" title="Google supplier" accent="emerald" />
              <RegistryPanel supplier="openai" title="OpenAI supplier" accent="violet" />
            </div>
          </div>

          {/* Secure Vault Section (disabled here; keys are server-side in production) */}
          <div className="p-8 bg-zinc-900 border border-white/10 rounded-3xl shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <i className="fas fa-shield-halved text-6xl text-emerald-500"></i>
            </div>

            <div className="relative z-10">
              <div className="mb-6">
                <h3 className="text-[10px] font-black uppercase tracking-[0.4em] text-emerald-500 mb-2">Secure Vault</h3>
                <p className="text-xl font-bold text-white uppercase tracking-tight">API Interface Credentials</p>
                <p className="text-[10px] text-zinc-500 mt-1 uppercase font-medium">
                  Keys are managed server-side (Secret Manager in production). No browser persistence.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-[9px] uppercase font-black text-zinc-600 mb-2">Google (Gemini)</p>
                  <input
                    value="Managed by server"
                    disabled
                    className="w-full bg-black/50 border border-white/10 rounded-2xl px-6 py-4 text-sm font-mono text-emerald-400 opacity-60 cursor-not-allowed"
                  />
                </div>

                <div>
                  <p className="text-[9px] uppercase font-black text-zinc-600 mb-2">OpenAI</p>
                  <input
                    value="Managed by server"
                    disabled
                    className="w-full bg-black/50 border border-white/10 rounded-2xl px-6 py-4 text-sm font-mono text-violet-300 opacity-60 cursor-not-allowed"
                  />
                </div>
              </div>

              <p className="mt-4 text-[9px] text-zinc-600 uppercase font-bold tracking-widest">
                Local development: set GEMINI_API_KEY / OPENAI_API_KEY in your environment (or .env).
              </p>
            </div>
          </div>
          {/* End Secure Vault */}
        </div>
      </div>
    </div>
  );
};
