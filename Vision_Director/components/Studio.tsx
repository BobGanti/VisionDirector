import React, { useEffect, useRef, useState } from 'react';
import { AppStatus } from '../types';
import type { MediaAsset, VoiceProfile, AspectRatio, SpeechSpeed, Sentiment } from '../types';
import { getAIProvider, type VideoSeconds } from '../services/aiProvider';

import { AssetCard } from './AssetCard';
import { LoadingOverlay } from './LoadingOverlay';
import { ModelMap } from './ModelMap';
import { blobToBase64 } from '../utils/audioUtils';

export type Supplier = 'google' | 'openai';

export type ScopedCustomVoice = {
  id: string;
  supplier: Supplier;
  label: string;
  baseVoice: VoiceProfile;
  traits: string;
  speed: SpeechSpeed;
  sentiment?: Sentiment;
};

export const GOOGLE_VOICES: { id: VoiceProfile; label: string }[] = [
  // Keep Zephyr first so fallbacks/defaults stay sensible
  { id: 'Zephyr', label: 'ZEPHYR (F)' },
  { id: 'Kore', label: 'KORE (F)' },
  { id: 'Puck', label: 'PUCK (M)' },
  { id: 'Charon', label: 'CHARON (M)' },
  { id: 'Fenrir', label: 'FENRIR (M)' },

  // Full Gemini-TTS voice list (30 total)
  { id: 'Achernar', label: 'ACHERNAR (F)' },
  { id: 'Achird', label: 'ACHIRD (M)' },
  { id: 'Algenib', label: 'ALGENIB (M)' },
  { id: 'Algieba', label: 'ALGIEBA (M)' },
  { id: 'Alnilam', label: 'ALNILAM (M)' },
  { id: 'Aoede', label: 'AOEDE (F)' },
  { id: 'Autonoe', label: 'AUTONOE (F)' },
  { id: 'Callirrhoe', label: 'CALLIRRHOE (F)' },
  { id: 'Despina', label: 'DESPINA (F)' },
  { id: 'Enceladus', label: 'ENCELADUS (M)' },
  { id: 'Erinome', label: 'ERINOME (F)' },
  { id: 'Gacrux', label: 'GACRUX (F)' },
  { id: 'Iapetus', label: 'IAPETUS (M)' },
  { id: 'Laomedeia', label: 'LAOMEDEIA (F)' },
  { id: 'Leda', label: 'LEDA (F)' },
  { id: 'Orus', label: 'ORUS (M)' },
  { id: 'Pulcherrima', label: 'PULCHERRIMA (F)' },
  { id: 'Rasalgethi', label: 'RASALGETHI (M)' },
  { id: 'Sadachbia', label: 'SADACHBIA (M)' },
  { id: 'Sadaltager', label: 'SADALTAGER (M)' },
  { id: 'Schedar', label: 'SCHEDAR (M)' },
  { id: 'Sulafat', label: 'SULAFAT (F)' },
  { id: 'Umbriel', label: 'UMBRIEL (M)' },
  { id: 'Vindemiatrix', label: 'VINDEMIATRIX (F)' },
  { id: 'Zubenelgenubi', label: 'ZUBENELGENUBI (M)' },
];

export const OPENAI_VOICES: { id: VoiceProfile; label: string }[] = [
  { id: 'alloy', label: 'ALLOY' },
  { id: 'echo', label: 'ECHO' },
  { id: 'fable', label: 'FABLE' },
  { id: 'onyx', label: 'ONYX' },
  { id: 'nova', label: 'NOVA' },
  { id: 'shimmer', label: 'SHIMMER' },
  { id: 'verse', label: 'VERSE' },
  { id: 'ash', label: 'ASH' },
  { id: 'sage', label: 'SAGE' },
  { id: 'ballad', label: 'BALLAD' },
  { id: 'coral', label: 'CORAL' },
];

export const SUPPLIERS: { id: Supplier; uiLabel: string }[] = [
  { id: 'google', uiLabel: 'GOOGLE' },
  { id: 'openai', uiLabel: 'OPENAI' },
];

const Studio: React.FC<{ isBridgeMode?: boolean }> = ({ isBridgeMode = false }) => {
  const [vaultOpen, setVaultOpen] = useState(false);

  // DB-backed supplier (no localStorage). Default Google until server responds.
  const [supplier, setSupplier] = useState<Supplier>('google');

  // Asset vault persistence (NOT API keys). This is unchanged from your earlier design.
  const [assets, setAssets] = useState<MediaAsset[]>(() => {
    try {
      const saved = localStorage.getItem('vision_studio_assets_v23');
      const parsed = saved ? JSON.parse(saved) : [];
      return Array.isArray(parsed) ? parsed.filter((a: any) => a?.url && String(a.url).length > 0) : [];
    } catch {
      return [];
    }
  });

  // DB-backed custom voices (supplier-scoped). No localStorage.
  const [customVoices, setCustomVoices] = useState<ScopedCustomVoice[]>([]);

  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedAudioId, setSelectedAudioId] = useState<string | null>(null);

  // Voice state
  const [activeVoice, setActiveVoice] = useState<VoiceProfile>('Zephyr');
  const [activeCustomVoiceId, setActiveCustomVoiceId] = useState<string | null>(null);

  // Duration (supplier-aware)
  const [videoSeconds, setVideoSeconds] = useState<VideoSeconds>('8');

  const [speechSpeed, setSpeechSpeed] = useState<SpeechSpeed>('natural');
  const [sentiment, setSentiment] = useState<Sentiment>('neutral');
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>('9:16');

  const [prompt, setPrompt] = useState('');
  const [status, setStatus] = useState<AppStatus>(AppStatus.IDLE);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showBlueprint, setShowBlueprint] = useState(false);

  const activeAsset = assets.find((a) => a.id === selectedAssetId) || null;
  const activeAudio = assets.find((a) => a.type === 'audio' && a.id === selectedAudioId) || null;
  const isExtensionMode = activeAsset?.type === 'video' && !!activeAsset.videoRef;

  const showError = (msg: string) => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 8000);
  };

  const downloadSelectedVideo = () => {
    const target = activeAsset?.type === 'video' ? activeAsset : null;
    if (!target?.url) return showError('NO VIDEO SELECTED TO DOWNLOAD.');

    const a = document.createElement('a');
    a.href = target.url;
    a.download = target.fileName || 'video.mp4';
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  // Theme (Light/Dark)
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [uiScale, setUiScale] = useState<'normal' | 'large'>('normal');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const LOGO_STORAGE_KEY = 'vd_brand_logo_v1';

  const [brandLogo, setBrandLogo] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LOGO_STORAGE_KEY);
    } catch {
      return null;
    }
  });

  useEffect(() => {
    const refresh = () => {
      try {
        setBrandLogo(localStorage.getItem(LOGO_STORAGE_KEY));
      } catch {
        // ignore
      }
    };

    refresh();
    window.addEventListener('vd-logo-updated', refresh as any);
    return () => window.removeEventListener('vd-logo-updated', refresh as any);
  }, []);


  const DURATION_OPTIONS: VideoSeconds[] = supplier === 'openai' ? ['4', '8', '12'] : ['8'];

  // Apply theme class
  useEffect(() => {
    document.body.classList.toggle('vd-light', theme === 'light');
    return () => document.body.classList.remove('vd-light');
  }, [theme]);

  useEffect(() => {
    document.body.classList.toggle('vd-large', uiScale === 'large');
    return () => document.body.classList.remove('vd-large');
  }, [uiScale]);

  // Load supplier from DB on launch
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch('/api/settings/supplier', { method: 'GET' });
        if (!res.ok) return;
        const data = await res.json().catch(() => null);
        const s: Supplier = data?.supplier === 'openai' ? 'openai' : 'google';
        if (!cancelled) setSupplier(s);
      } catch {
        // keep default google
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch('/api/settings/ui-scale', { method: 'GET' });
        if (!res.ok) return;
        const data = await res.json().catch(() => null);
        const s = data?.uiScale === 'large' ? 'large' : 'normal';
        if (!cancelled) setUiScale(s);
      } catch {
        // keep default
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch('/api/settings/theme', { method: 'GET' });
        if (!res.ok) return;
        const data = await res.json().catch(() => null);
        const t = data?.theme === 'light' ? 'light' : 'dark';
        if (!cancelled) setTheme(t);
      } catch {
        // keep default
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const persistUiScale = async (next: 'normal' | 'large') => {
    setUiScale(next);
    try {
      const res = await fetch('/api/settings/ui-scale', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uiScale: next }),
      });
      if (!res.ok) {
        const t = await res.text().catch(() => '');
        throw new Error(t || `${res.status} ${res.statusText}`);
      }
    } catch (e: any) {
      showError(`FAILED TO SAVE UI SCALE: ${String(e?.message || e || '')}`);
    }
  };

  const persistTheme = async (next: 'dark' | 'light') => {
    setTheme(next); // optimistic
    try {
      const res = await fetch('/api/settings/theme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme: next }),
      });

      if (!res.ok) {
        const t = await res.text().catch(() => '');
        throw new Error(t || `${res.status} ${res.statusText}`);
      }
    } catch (e: any) {
      showError(`FAILED TO SAVE THEME: ${String(e?.message || e || '')}`);
    }
  };

  // Persist supplier to DB (called by dropdowns)
  const persistSupplier = async (next: Supplier) => {
    setSupplier(next); // optimistic
    try {
      const res = await fetch('/api/settings/supplier', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ supplier: next }),
      });

      if (!res.ok) {
        const t = await res.text().catch(() => '');
        throw new Error(t || `${res.status} ${res.statusText}`);
      }
    } catch (e: any) {
      showError(`FAILED TO SAVE SUPPLIER: ${String(e?.message || e || '')}`);
    }
  };

  const ai = getAIProvider(supplier as any);
  const voiceOptions = supplier === 'openai' ? OPENAI_VOICES : GOOGLE_VOICES;

  // When supplier changes:
  // - prevent cross-supplier identity carry-over
  // - ensure activeVoice is valid
  // - clamp duration to supplier allowed values (Google fixed to 8s)
  useEffect(() => {
    setActiveCustomVoiceId(null);

    const ok = voiceOptions.some((v) => v.id === activeVoice);
    if (!ok) setActiveVoice(voiceOptions[0]?.id || 'Zephyr');

    if (supplier === 'openai') {
      if (!['4', '8', '12'].includes(videoSeconds)) setVideoSeconds('8');
    } else {
      if (videoSeconds !== '8') setVideoSeconds('8');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplier]);

  // Load supplier-scoped identities from DB whenever supplier changes
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`/api/voice-identities/${supplier}`);
        if (!res.ok) throw new Error(await res.text());

        const data = await res.json();
        const raw = Array.isArray(data?.voices) ? data.voices : [];

        const voices: ScopedCustomVoice[] = raw.map((v: any) => ({
          id: String(v.id),
          supplier: (v.supplier === 'openai' ? 'openai' : 'google') as Supplier,
          label: String(v.label || '').toUpperCase(),
          baseVoice: (v.baseVoice ?? v.base_voice ?? 'Zephyr') as VoiceProfile,
          traits: String(v.traits || ''),
          speed: (v.speed || 'natural') as SpeechSpeed,
          sentiment: (v.sentiment || undefined) as Sentiment | undefined,
        }));

        if (!cancelled) setCustomVoices(voices);
      } catch {
        if (!cancelled) setCustomVoices([]);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [supplier]);

  // Keep assets persistence (unchanged), but make it safe
  useEffect(() => {
    try {
      // NEVER persist videos or huge base64 payloads to localStorage
      const safeAssets = assets
        .filter((a) => a.type !== 'video')
        .map((a) => ({ ...a, videoRef: undefined }))
        .filter((a) => typeof a.url === 'string' && (!a.url.startsWith('data:') || a.url.length < 200_000));

      localStorage.setItem('vision_studio_assets_v23', JSON.stringify(safeAssets));
    } catch (err) {
      console.warn('[VisionDirector] Skipped asset persistence:', err);
    }
  }, [assets]);

  // Close mobile vault on ESC
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setVaultOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Fix: fullscreen video in vd-light can appear "negative" because body filter applies but video undo doesn't.
  // When a VIDEO enters fullscreen, temporarily disable the body filter.
  useEffect(() => {
    const onFsChange = () => {
      const el = document.fullscreenElement as any;
      const isVideo = !!el && String(el?.tagName || '').toUpperCase() === 'VIDEO';
      document.body.classList.toggle('vd-fs-media', isVideo);
    };

    document.addEventListener('fullscreenchange', onFsChange);

    // Safari/older WebKit (safe even if never fired)
    document.addEventListener('webkitfullscreenchange' as any, onFsChange);

    return () => {
      document.removeEventListener('fullscreenchange', onFsChange);
      document.removeEventListener('webkitfullscreenchange' as any, onFsChange);
      document.body.classList.remove('vd-fs-media');
    };
  }, []);


  const handleExecuteRender = async () => {
    try {
      setStatus(isExtensionMode ? AppStatus.EXTENDING_VIDEO : AppStatus.ANALYZING_SCRIPT);
      const script = await ai.parseScript(prompt);

      let img1 = activeAsset?.type === 'image' ? activeAsset : null;
      const extensionRef = isExtensionMode ? activeAsset?.videoRef : null;

      if (!img1 && !activeAudio && !extensionRef && prompt) {
        setStatus(AppStatus.GENERATING_IMAGE);
        const genImg = await ai.generateImage(script.visuals || prompt, aspectRatio);
        if (genImg) {
          const newAsset: MediaAsset = {
            id: `gen-${Date.now()}`,
            type: 'image' as const,
            url: genImg,
            timestamp: Date.now(),
            fileName: 'GEN_REF.png',
          };
          setAssets((prev) => [newAsset, ...prev]);
          img1 = newAsset;
        }
      }

      let voiceTraits = '';
      if (activeAudio) {
        setStatus(AppStatus.GENERATING_AUDIO);
        voiceTraits = await ai.analyseVoice(activeAudio.url, sentiment);
        if (!script.narration) {
          script.narration = await ai.transcribeAudio(activeAudio.url);
        }
      } else if (activeCustomVoiceId) {
        voiceTraits = customVoices.find((v) => v.id === activeCustomVoiceId)?.traits || '';
      }

      setStatus(AppStatus.GENERATING_VIDEO);
      const videoResult = await ai.generateVideo(
        script.visuals,
        script.narration,
        aspectRatio,
        img1?.url,
        voiceTraits,
        activeVoice,
        speechSpeed,
        sentiment,
        extensionRef,
        videoSeconds // ✅ IMPORTANT: this makes the dropdown actually work
      );

      if (videoResult) {
        const vidAsset: MediaAsset = {
          id: `vid-${Date.now()}`,
          type: 'video' as const,
          url: videoResult.url,
          videoRef: videoResult.videoRef,
          timestamp: Date.now(),
          fileName: isExtensionMode ? 'EXT_SEQ.mp4' : 'FINAL.mp4',
        };
        setAssets((prev) => [vidAsset, ...prev]);
        setSelectedAssetId(vidAsset.id);
      }
    } catch (e: any) {
      showError(e?.message || 'FAILED');
    } finally {
      setStatus(AppStatus.IDLE);
    }
  };

  const handleSaveIdentity = async () => {
    if (!activeAudio) return showError('SELECT AUDIO ASSET FIRST.');
    const label = window.prompt('NAME IDENTITY:');
    if (!label) return;

    setStatus(AppStatus.GENERATING_AUDIO);
    try {
      const traits = await ai.analyseVoice(activeAudio.url, sentiment);

      const res = await fetch(`/api/voice-identities/${supplier}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label,
          baseVoice: activeVoice,
          traits,
          speed: speechSpeed,
          sentiment,
        }),
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const v = data?.voice;

      const saved: ScopedCustomVoice = {
        id: String(v.id),
        supplier,
        label: String(v.label || label).toUpperCase(),
        baseVoice: (v.baseVoice ?? v.base_voice ?? activeVoice) as VoiceProfile,
        traits: String(v.traits || traits),
        speed: (v.speed || speechSpeed) as SpeechSpeed,
        sentiment: (v.sentiment || sentiment) as Sentiment,
      };

      setCustomVoices((prev) => [saved, ...prev]);
      setActiveCustomVoiceId(saved.id);

      await ai.playVoicePreview(saved.baseVoice, saved.speed, saved.traits, 'Identity Captured.');
    } catch (e: any) {
      showError(String(e?.message || e || 'Cloning failed.'));
    } finally {
      setStatus(AppStatus.IDLE);
    }
  };

  const handlePreviewVoice = async () => {
    if (status !== AppStatus.IDLE) return;

    setStatus(AppStatus.GENERATING_AUDIO);
    try {
      if (activeCustomVoiceId) {
        const cv = customVoices.find((v) => v.id === activeCustomVoiceId);
        if (!cv) throw new Error('VOICE_PROFILE_NOT_FOUND');
        await ai.playVoicePreview(cv.baseVoice, cv.speed, cv.traits, `Preview: ${cv.label}.`);
      } else {
        let traits = '';
        if (activeAudio) {
          traits = await ai.analyseVoice(activeAudio.url, sentiment);
        }
        await ai.playVoicePreview(activeVoice, speechSpeed, traits, `Preview: ${String(activeVoice).toUpperCase()}.`);
      }
    } catch (e: any) {
      showError(e?.message || 'Preview failed.');
    } finally {
      setStatus(AppStatus.IDLE);
    }
  };

  const deleteIdentity = async (id: string) => {
    try {
      const res = await fetch(`/api/voice-identities/${supplier}/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      setCustomVoices((prev) => prev.filter((v) => v.id !== id));
      if (activeCustomVoiceId === id) setActiveCustomVoiceId(null);
    } catch (e: any) {
      showError(`DELETE FAILED: ${String(e?.message || e)}`);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const base64 = await blobToBase64(file);
    const type = file.type.startsWith('image') ? 'image' : file.type.startsWith('video') ? 'video' : 'audio';

    const newAsset: MediaAsset = {
      id: `asset-${Date.now()}`,
      type: type as any,
      url: `data:${file.type};base64,${base64}`,
      timestamp: Date.now(),
      fileName: file.name,
    };

    setAssets((prev) => [newAsset, ...prev]);
    if (type === 'audio') setSelectedAudioId(newAsset.id);
    else setSelectedAssetId(newAsset.id);
  };

  const headerTitle = isBridgeMode ? 'VisionDirector (Bridge)' : 'VisionDirector';

  return (
    <div className="vd-ui relative flex flex-col md:flex-row min-h-[100svh] md:h-screen bg-[var(--bg)] text-zinc-100 font-inter overflow-x-hidden overflow-y-auto md:overflow-y-auto">
      <LoadingOverlay status={status} />
      {showBlueprint && <ModelMap onClose={() => setShowBlueprint(false)} />}

      {/* Mobile backdrop when the Asset Vault is open */}
      {vaultOpen && (
        <button
          type="button"
          aria-label="Close Asset Vault"
          className="md:hidden fixed inset-0 z-[90]"
          style={{ background: 'var(--backdrop)' }}
          onClick={() => setVaultOpen(false)}
        />
      )}

      {errorMsg && (
        <div className="fixed top-10 left-1/2 -translate-x-1/2 z-[200] bg-red-600 px-6 py-3 rounded-xl shadow-2xl font-black uppercase text-[10px] tracking-widest">
          <i className="fa-solid fa-triangle-exclamation mr-2"></i>
          {errorMsg}
        </div>
      )}

      {/* Asset Vault (desktop sidebar) */}
      <aside className="hidden md:flex md:w-72 border-r border-white/5 bg-[var(--surface)] flex-col shrink-0">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-[10px] font-black uppercase tracking-widest text-violet-500">Asset Vault</h2>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-8 h-8 bg-white/5 rounded-lg flex items-center justify-center hover:bg-violet-600 transition-all"
            >
              <i className="fa-solid fa-plus text-[10px]"></i>
            </button>
            <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileUpload} />
          </div>

          <div className="space-y-4 max-h-[calc(100vh-100px)] overflow-y-auto scrollbar-hide">
            {assets.length === 0 && (
              <div className="p-6 border border-dashed border-white/5 rounded-2xl opacity-20 text-center">
                <i className="fa-solid fa-cloud-arrow-up text-xl mb-2"></i>
                <p className="text-[8px] uppercase font-black tracking-widest leading-relaxed">
                  Vault Empty.
                  <br />
                  Upload Media Assets.
                </p>
              </div>
            )}
            {assets.map((asset) => (
              <AssetCard
                key={asset.id}
                asset={asset}
                isSelected={selectedAssetId === asset.id || selectedAudioId === asset.id}
                onSelect={(a) =>
                  a.type === 'audio'
                    ? setSelectedAudioId(a.id === selectedAudioId ? null : a.id)
                    : setSelectedAssetId(a.id === selectedAssetId ? null : a.id)
                }
                onDelete={(id) => setAssets((prev) => prev.filter((a) => a.id !== id))}
              />
            ))}
          </div>
        </div>
      </aside>

      {/* Mobile drawer version of Asset Vault */}
      {vaultOpen && (
        <aside className="md:hidden fixed inset-y-0 left-0 z-[100] w-[85vw] max-w-sm border-r border-white/10 bg-[var(--surface)] flex flex-col">
          <div className="p-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-[10px] font-black uppercase tracking-widest text-violet-500">Asset Vault</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-9 h-9 bg-white/5 rounded-lg flex items-center justify-center hover:bg-violet-600 transition-all"
                  aria-label="Upload"
                >
                  <i className="fa-solid fa-plus text-[11px]"></i>
                </button>
                <button
                  onClick={() => setVaultOpen(false)}
                  className="w-9 h-9 bg-white/5 rounded-lg flex items-center justify-center hover:bg-white/10 transition-all"
                  aria-label="Close"
                >
                  <i className="fa-solid fa-xmark text-[12px]"></i>
                </button>
              </div>
              <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileUpload} />
            </div>

            <div className="space-y-3 max-h-[calc(100svh-110px)] overflow-y-auto scrollbar-hide pr-1">
              {assets.length === 0 && (
                <div className="p-6 border border-dashed border-white/5 rounded-2xl opacity-20 text-center">
                  <i className="fa-solid fa-cloud-arrow-up text-xl mb-2"></i>
                  <p className="text-[8px] uppercase font-black tracking-widest leading-relaxed">
                    Vault Empty.
                    <br />
                    Upload Media Assets.
                  </p>
                </div>
              )}
              {assets.map((asset) => (
                <AssetCard
                  key={asset.id}
                  asset={asset}
                  isSelected={selectedAssetId === asset.id || selectedAudioId === asset.id}
                  onSelect={(a) => {
                    if (a.type === 'audio') setSelectedAudioId(a.id === selectedAudioId ? null : a.id);
                    else setSelectedAssetId(a.id === selectedAssetId ? null : a.id);
                    setVaultOpen(false);
                  }}
                  onDelete={(id) => setAssets((prev) => prev.filter((a) => a.id !== id))}
                />
              ))}
            </div>
          </div>
        </aside>
      )}

      <main className="flex flex-col min-w-0 flex-none md:flex-1">
        <header className="h-14 px-4 md:px-6 flex items-center justify-between border-b border-white/5 bg-[var(--surface)]">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all overflow-hidden ring-1 ring-white/10 ${
              isExtensionMode ? 'bg-emerald-600 shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'bg-violet-600'
            }`}
            title="Logo (set in Model Blueprint → Secure Vault)"
            aria-label="App logo"
          >
            {brandLogo ? (
              <img src={brandLogo} alt="Logo" className="w-full h-full object-contain" />
            ) : (
              <i className={`fa-solid ${isExtensionMode ? 'fa-forward-step' : 'fa-clapperboard'} text-white text-[12px]`}></i>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Download (higher contrast in both dark + light) */}
            <button
              onClick={downloadSelectedVideo}
              disabled={!activeAsset || activeAsset.type !== 'video'}
              className="h-9 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 hover:text-white flex items-center gap-2 transition-all disabled:opacity-25 disabled:pointer-events-none"
              title={activeAsset?.type === 'video' ? 'Download selected video' : 'Generate or select a video to download'}
              aria-label="Download video"
            >
              <i className="fa-solid fa-download text-[12px]"></i>
              <span className="text-[10px] font-black uppercase tracking-widest">
                {activeAsset?.type === 'video' ? 'Download' : 'No Video'}
              </span>
            </button>

            <button
              onClick={() => persistUiScale(uiScale === 'large' ? 'normal' : 'large')}
              className="h-10 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-400 hover:text-white transition-all"
              title={uiScale === 'large' ? 'Switch to normal text size' : 'Switch to larger text size'}
              aria-label="Toggle text size"
            >
              <span className="text-[11px] font-black uppercase tracking-widest">{uiScale === 'large' ? 'A-' : 'A+'}</span>
            </button>

            <button
              onClick={() => persistTheme(theme === 'light' ? 'dark' : 'light')}
              className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-zinc-500 hover:text-white transition-all"
              title={theme === 'light' ? 'Switch to Dark' : 'Switch to Light'}
              aria-label="Toggle theme"
            >
              <i className={`fa-solid ${theme === 'light' ? 'fa-moon' : 'fa-sun'}`}></i>
            </button>

            <button
              onClick={() => setShowBlueprint(true)}
              className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-zinc-500 hover:text-white transition-all"
              title="Model Blueprint"
              aria-label="Open Model Blueprint"
            >
              <i className="fa-solid fa-share-nodes"></i>
            </button>
          </div>
        </header>

        {/* Monitor */}
        <div className="bg-[var(--surface)] flex flex-col items-center justify-center p-4 md:p-8 overflow-hidden relative flex-none md:flex-none h-[52svh] sm:h-[56svh] md:h-[62vh] md:min-h-[560px]">
          <div
            style={{ aspectRatio: aspectRatio.replace(':', '/') }}
            className="w-full h-full max-w-4xl md:max-w-6xl bg-[var(--panel)] rounded-3xl shadow-2xl ring-1 ring-white/10 overflow-hidden flex items-center justify-center relative group"
          >
            {activeAsset ? (
              activeAsset.type === 'video' ? (
                <video src={activeAsset.url} className="w-full h-full object-contain" autoPlay loop controls />
              ) : (
                <img src={activeAsset.url} className="w-full h-full object-contain" />
              )
            ) : (
              <div className="flex flex-col items-center gap-4 opacity-10">
                <i className="fa-solid fa-film text-6xl"></i>
                <span className="text-[10px] font-black uppercase tracking-[1em]">Monitor Offline</span>
              </div>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="p-4 md:p-8 border-t border-white/5 bg-[var(--panel)] overflow-y-auto md:overflow-visible">
          <div className="w-full">
            <div className="flex flex-col md:flex-row gap-4 md:gap-6 mb-6 md:mb-8">
              <div className="flex-1 space-y-3">
                {/* ===== DESKTOP LAYOUT FIX START ===== */}
                <div className="px-1 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-[9px] font-black uppercase tracking-widest text-zinc-400">
                      {isExtensionMode ? 'Extension Script' : 'Sequence Narrative'}
                    </span>
                    {activeAudio && (
                      <span className="text-[7px] font-black bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-full uppercase tracking-tighter border border-emerald-500/20">
                        DNA ACTIVE — base voice selectable
                      </span>
                    )}
                  </div>
                </div>     

                {/* Desktop controls — single aligned row */}
                <div className="hidden sm:grid px-1 grid-cols-2 md:grid-cols-5 gap-3 md:gap-4 items-end">
                  <div className="flex flex-col gap-1 min-w-0">
                    <span className="text-[7px] font-black text-zinc-500 uppercase">Supplier</span>
                    <select
                      value={supplier}
                      onChange={(e) => persistSupplier(e.target.value as Supplier)}
                      className="w-full bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-sky-400 outline-none"
                    >
                      {SUPPLIERS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.uiLabel}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1 min-w-0">
                    <span className="text-[7px] font-black text-zinc-500 uppercase">Aspect</span>
                    <select
                      value={aspectRatio}
                      onChange={(e) => setAspectRatio(e.target.value as AspectRatio)}
                      className="w-full bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-emerald-400 outline-none"
                    >
                      <option value="9:16">9:16 PORTRAIT</option>
                      <option value="16:9">16:9 LANDSCAPE</option>
                      <option value="1:1">1:1 SQUARE</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1 min-w-0">
                    <span className="text-[7px] font-black text-zinc-500 uppercase">Speed</span>
                    <select
                      value={speechSpeed}
                      onChange={(e) => setSpeechSpeed(e.target.value as SpeechSpeed)}
                      className="w-full bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-amber-400 outline-none"
                    >
                      <option value="slower">SLOWER</option>
                      <option value="slow">SLOW</option>
                      <option value="natural">NATURAL</option>
                      <option value="fast">FAST</option>
                      <option value="faster">FASTER</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1 min-w-0">
                    <span className="text-[7px] font-black text-zinc-500 uppercase">Duration</span>
                    <select
                      value={videoSeconds}
                      onChange={(e) => setVideoSeconds(e.target.value as VideoSeconds)}
                      className="w-full bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-cyan-300 outline-none"
                    >
                      {DURATION_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}s
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1 min-w-0">
                    <span className="text-[7px] font-black text-zinc-500 uppercase">Sentiment</span>
                    <select
                      value={sentiment}
                      onChange={(e) => setSentiment(e.target.value as Sentiment)}
                      className="w-full bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-violet-400 outline-none"
                    >
                      {['neutral', 'cinematic', 'aggressive', 'whispering', 'joyful', 'somber'].map((s) => (
                        <option key={s} value={s}>
                          {s.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Mobile controls — RESTORED to the original 2-row layout (not distorted) */}
                <div className="sm:hidden px-1 space-y-3">
                  <div className="flex gap-3">
                    <select
                      value={supplier}
                      onChange={(e) => persistSupplier(e.target.value as Supplier)}
                      className="flex-1 bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-sky-400 outline-none"
                    >
                      {SUPPLIERS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.uiLabel}
                        </option>
                      ))}
                    </select>

                    <select
                      value={aspectRatio}
                      onChange={(e) => setAspectRatio(e.target.value as AspectRatio)}
                      className="flex-1 bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-emerald-400 outline-none"
                    >
                      <option value="9:16">9:16</option>
                      <option value="16:9">16:9</option>
                      <option value="1:1">1:1</option>
                    </select>

                    <select
                      value={videoSeconds}
                      onChange={(e) => setVideoSeconds(e.target.value as VideoSeconds)}
                      className="flex-1 bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-cyan-300 outline-none"
                    >
                      {DURATION_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}s
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex gap-3">
                    <select
                      value={speechSpeed}
                      onChange={(e) => setSpeechSpeed(e.target.value as SpeechSpeed)}
                      className="flex-1 bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-amber-400 outline-none"
                    >
                      <option value="slower">SLOWER</option>
                      <option value="slow">SLOW</option>
                      <option value="natural">NATURAL</option>
                      <option value="fast">FAST</option>
                      <option value="faster">FASTER</option>
                    </select>

                    <select
                      value={sentiment}
                      onChange={(e) => setSentiment(e.target.value as Sentiment)}
                      className="flex-1 bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-violet-400 outline-none"
                    >
                      {['neutral', 'cinematic', 'aggressive', 'whispering', 'joyful', 'somber'].map((s) => (
                        <option key={s} value={s}>
                          {s.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>


                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className={`w-full h-28 md:h-24 bg-white/5 rounded-2xl p-4 md:p-6 text-sm font-medium border focus:border-violet-500/50 outline-none transition-all resize-none shadow-inner ${
                    isExtensionMode ? 'border-emerald-500/30' : 'border-white/5'
                  }`}
                  placeholder={
                    isExtensionMode ? 'Describe the next sequence of actions precisely...' : '[Shot Type] Subject details... "Narration goes here"'
                  }
                />
              </div>

              <div className="w-full md:w-64 flex flex-col justify-end">
                <button
                  onClick={handleExecuteRender}
                  disabled={status !== AppStatus.IDLE}
                  className={`w-full h-16 md:h-24 rounded-2xl flex flex-col items-center justify-center gap-2 transition-all shadow-2xl disabled:opacity-20 text-white font-black uppercase tracking-widest text-[10px] ${
                    isExtensionMode
                      ? 'bg-emerald-600 hover:bg-emerald-500 shadow-[0_10px_30px_rgba(16,185,129,0.3)]'
                      : 'bg-violet-600 hover:bg-violet-500 shadow-[0_10px_30px_rgba(139,92,246,0.3)]'
                  }`}
                >
                  <i className={`fa-solid ${isExtensionMode ? 'fa-forward-step animate-pulse' : 'fa-play'}`}></i>
                  {isExtensionMode ? 'Extend Sequence' : 'Execute Render'}
                </button>
              </div>
            </div>

            <div className="flex flex-col md:flex-row md:items-center justify-between border-t border-white/5 pt-6 gap-4 md:gap-0">
              <div className="flex items-center gap-6 overflow-hidden flex-1">
                <div className="shrink-0 flex flex-col">
                  <span className="text-[9px] font-black uppercase text-zinc-400 tracking-widest">Identity Vault</span>
                  <span className="text-[7px] text-zinc-400 font-bold uppercase">{activeAudio ? 'DNA ACTIVE' : 'PREBUILT'}</span>
                </div>

                <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide pr-8">
                  {customVoices.map((cv) => (
                    <div key={cv.id} className="flex items-center shrink-0">
                      <button
                        onClick={() => {
                          setActiveCustomVoiceId(cv.id);
                          setActiveVoice(cv.baseVoice);
                          setSpeechSpeed(cv.speed);
                          if (cv.sentiment) setSentiment(cv.sentiment);
                        }}
                        className={`px-4 py-2 rounded-l-xl text-[9px] font-black tracking-widest flex items-center gap-2 transition-all ${
                          activeCustomVoiceId === cv.id ? 'bg-emerald-600 text-white shadow-lg' : 'bg-white/5 text-emerald-500/60 hover:bg-white/10'
                        }`}
                        title="Select identity"
                        type="button"
                      >
                        <i className="fa-solid fa-fingerprint"></i>
                        {cv.label}
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();

                          const ok = window.confirm(`Delete identity "${cv.label}"?`);
                          if (!ok) return;

                          deleteIdentity(cv.id);
                        }}
                        className={`px-3 py-2 rounded-r-xl border-l border-white/10 transition-all ${
                          activeCustomVoiceId === cv.id ? 'bg-emerald-600/90 text-white hover:bg-emerald-600' : 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10'
                        }`}
                        title="Delete identity"
                        aria-label={`Delete ${cv.label}`}
                      >
                        <i className="fa-solid fa-trash-can text-[10px]"></i>
                      </button>
                    </div>
                  ))}

                  <div className="w-[1px] h-6 bg-white/10 shrink-0 mx-2"></div>

                  {voiceOptions.map((v) => (
                    <button
                      key={String(v.id)}
                      onClick={() => {
                        // Selecting base voice does NOT clear selected DNA audio.
                        setActiveCustomVoiceId(null);
                        setActiveVoice(v.id);
                      }}
                      className={`px-4 py-2 rounded-xl text-[9px] font-black tracking-widest shrink-0 transition-all ${
                        activeVoice === v.id && !activeCustomVoiceId ? 'bg-violet-600 text-white shadow-lg' : 'bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10'
                      }`}
                      title={activeAudio ? 'Select base voice (DNA remains active)' : 'Select voice'}
                      type="button"
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 shrink-0">
                <button
                  onClick={handlePreviewVoice}
                  disabled={status !== AppStatus.IDLE}
                  className="px-6 py-2 rounded-xl border border-white/5 text-[9px] font-black uppercase text-zinc-500 hover:text-violet-300 transition-all bg-white/[0.02] hover:bg-violet-500/5 hover:border-violet-500/20 disabled:opacity-20 disabled:pointer-events-none"
                >
                  <i className="fa-solid fa-volume-high mr-2"></i>Preview Voice
                </button>

                <button
                  onClick={handleSaveIdentity}
                  disabled={status !== AppStatus.IDLE}
                  className="px-6 py-2 rounded-xl border border-white/5 text-[9px] font-black uppercase text-zinc-500 hover:text-emerald-400 transition-all bg-white/[0.02] hover:bg-emerald-500/5 hover:border-emerald-500/20 disabled:opacity-20 disabled:pointer-events-none"
                >
                  Capture Identity
                </button>
              </div>
            </div>

            {customVoices.length > 0 && (
              <div className="mt-3 text-[9px] text-zinc-500">
                Tip: use the <span className="font-black">trash</span> icon beside an identity to delete it.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Studio;
