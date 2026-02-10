import React, { useState, useRef, useEffect, type ReactFC } from 'react';
import { MediaAsset, AppStatus, VoiceProfile, AspectRatio, ParsedScript, CustomVoice, SpeechSpeed, Sentiment } from '../types';
import { getAIProvider } from '../services/aiProvider';
import { AssetCard } from './AssetCard';
import { LoadingOverlay } from './LoadingOverlay';
import { ModelMap } from './ModelMap';
import { blobToBase64 } from '../utils/audioUtils';

const DEFAULT_VOICES: { id: VoiceProfile; label: string }[] = [
  { id: 'Zephyr', label: 'ZEPHYR' },
  { id: 'Kore', label: 'KORE' },
  { id: 'Puck', label: 'PUCK' },
  { id: 'Charon', label: 'CHARON' },
  { id: 'Fenrir', label: 'FENRIR' },
  { id: 'Leda', label: 'LEDA' },
  { id: 'Orus', label: 'ORUS' },
  { id: 'Umbriel', label: 'UMBRIEL' },
  { id: 'Algieba', label: 'ALGIEBA' },
  { id: 'Enceladus', label: 'ENCELADUS' }
];

type Supplier = 'google' | 'openai';

const SUPPLIER_STORAGE_KEY = 'vision_studio_supplier_v23';

const SUPPLIERS: { id: Supplier; label: string; uiLabel: string }[] = [
  { id: 'google', label: 'Google', uiLabel: 'GOOGLE' },
  { id: 'openai', label: 'OpenAI', uiLabel: 'OPENAI' },
];


const Studio: React.FC<{ isBridgeMode?: boolean }> = ({ isBridgeMode = false }) => {
  const [vaultOpen, setVaultOpen] = useState(false);
  const [supplier, setSupplier] = useState<Supplier>(() => {
    const saved = localStorage.getItem(SUPPLIER_STORAGE_KEY);
    return saved === 'openai' ? 'openai' : 'google';
  });


  const [assets, setAssets] = useState<MediaAsset[]>(() => {
    try {
      const saved = localStorage.getItem('vision_studio_assets_v23');
      const parsed = saved ? JSON.parse(saved) : [];
      // Drop anything that has no usable URL (we won't persist videos anyway)
      return Array.isArray(parsed) ? parsed.filter((a: any) => a?.url && String(a.url).length > 0) : [];
    } catch {
      return [];
    }
  });

  const [customVoices, setCustomVoices] = useState<CustomVoice[]>(() => {
    try {
      const saved = localStorage.getItem('vision_studio_voices_v23');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedAudioId, setSelectedAudioId] = useState<string | null>(null);

  const [activeVoice, setActiveVoice] = useState<VoiceProfile>('Zephyr');
  const [activeCustomVoiceId, setActiveCustomVoiceId] = useState<string | null>(null);
  const [speechSpeed, setSpeechSpeed] = useState<SpeechSpeed>('natural');
  const [sentiment, setSentiment] = useState<Sentiment>('neutral');
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>('9:16');
  const [prompt, setPrompt] = useState('');
  const [status, setStatus] = useState<AppStatus>(AppStatus.IDLE);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showBlueprint, setShowBlueprint] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const ai = getAIProvider(supplier as any);

  const activeAsset = assets.find(a => a.id === selectedAssetId) || null;
  const activeAudio = assets.find(a => a.type === 'audio' && a.id === selectedAudioId) || null;
  const isExtensionMode = activeAsset?.type === 'video' && !!activeAsset.videoRef;

  useEffect(() => {
    try {
      const safeAssets = assets.map((a) => {
        // Never persist videos (can be huge / blob URLs won’t survive refresh anyway)
        if (a.type === "video") return null;

        // Also drop very large data URLs (usually audio) to avoid quota crashes
        if (typeof a.url === "string" && a.url.startsWith("data:") && a.url.length > 200_000) return null;

        return a;
      }).filter(Boolean);

      localStorage.setItem("vision_studio_assets_v23", JSON.stringify(safeAssets));
    } catch (e) {
      console.warn("[VisionDirector] Asset persistence skipped (localStorage quota).", e);
    }
  }, [assets]);

  useEffect(() => {
    try {
      // NEVER persist videos or huge base64 payloads to localStorage
      const safeAssets = assets
        .filter(a => a.type !== "video")
        .map(a => ({ ...a, videoRef: undefined })) // avoid huge/circular refs
        .filter(a => typeof a.url === "string" && (!a.url.startsWith("data:") || a.url.length < 200_000));

      localStorage.setItem("vision_studio_assets_v23", JSON.stringify(safeAssets));
    } catch (err) {
      // Critical: do not let quota errors crash the UI
      console.warn("[VisionDirector] Skipped asset persistence:", err);
    }
  }, [assets]);

  useEffect(() => {
  try {
    // NEVER persist videos or huge base64 payloads to localStorage
    const safeAssets = assets
      .filter(a => a.type !== "video")
      .map(a => ({ ...a, videoRef: undefined })) // avoid huge/circular refs
      .filter(a => typeof a.url === "string" && (!a.url.startsWith("data:") || a.url.length < 200_000));

    localStorage.setItem("vision_studio_assets_v23", JSON.stringify(safeAssets));
  } catch (err) {
      // Critical: do not let quota errors crash the UI
      console.warn("[VisionDirector] Skipped asset persistence:", err);
    }
  }, [assets]);

  const showError = (msg: string) => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 8000);
  };

  // Close the mobile Asset Vault when the user hits ESC.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setVaultOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const handleExecuteRender = async () => {
    try {
      setStatus(isExtensionMode ? AppStatus.EXTENDING_VIDEO : AppStatus.ANALYZING_SCRIPT);
      const script = await ai.parseScript(prompt);

      let img1 = activeAsset?.type === 'image' ? activeAsset : null;
      let extensionRef = isExtensionMode ? activeAsset?.videoRef : null;

      if (!img1 && !activeAudio && !extensionRef && prompt) {
        setStatus(AppStatus.GENERATING_IMAGE);
        const genImg = await ai.generateImage(script.visuals || prompt, aspectRatio);
        if (genImg) {
          const newAsset = { id: `gen-${Date.now()}`, type: 'image' as const, url: genImg, timestamp: Date.now(), fileName: "GEN_REF.png" };
          setAssets(prev => [newAsset, ...prev]);
          img1 = newAsset;
        }
      }

      let voiceTraits = "";
      if (activeAudio) {
        setStatus(AppStatus.GENERATING_AUDIO);
        voiceTraits = await ai.analyzeVoice(activeAudio.url, sentiment);
        if (!script.narration) {
          script.narration = await ai.transcribeAudio(activeAudio.url);
        }
      } else if (activeCustomVoiceId) {
        voiceTraits = customVoices.find(v => v.id === activeCustomVoiceId)?.traits || "";
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
        extensionRef
      );

      if (videoResult) {
        const vidAsset = { id: `vid-${Date.now()}`, type: 'video' as const, url: videoResult.url, videoRef: videoResult.videoRef, timestamp: Date.now(), fileName: isExtensionMode ? "EXT_SEQ.mp4" : "FINAL.mp4" };
        setAssets(prev => [vidAsset, ...prev]);
        setSelectedAssetId(vidAsset.id);
      }
    } catch (e: any) {
      showError(e.message);
    } finally {
      setStatus(AppStatus.IDLE);
    }
  };

  const handleSaveIdentity = async () => {
    if (!activeAudio) return showError("SELECT AUDIO ASSET FIRST.");
    const label = window.prompt("NAME IDENTITY:");
    if (!label) return;

    setStatus(AppStatus.GENERATING_AUDIO);
    try {
      const traits = await ai.analyzeVoice(activeAudio.url, sentiment);
      const newVoice = { id: `v-${Date.now()}`, label: label.toUpperCase(), baseVoice: activeVoice, traits, speed: speechSpeed, sentiment };
      setCustomVoices(prev => [newVoice, ...prev]);
      setActiveCustomVoiceId(newVoice.id);
      await ai.playVoicePreview(newVoice.baseVoice, newVoice.speed, newVoice.traits, `Identity Captured.`);
    } catch (e) {
      showError("Cloning failed.");
    } finally {
      setStatus(AppStatus.IDLE);
    }
  };

  const handlePreviewVoice = async () => {
    if (status !== AppStatus.IDLE) return;
    if (activeAudio) return showError("UNSELECT DNA AUDIO TO PREVIEW PREBUILT VOICES.");

    setStatus(AppStatus.GENERATING_AUDIO);
    try {
      if (activeCustomVoiceId) {
        const cv = customVoices.find(v => v.id === activeCustomVoiceId);
        if (!cv) throw new Error("VOICE_PROFILE_NOT_FOUND");
        await ai.playVoicePreview(cv.baseVoice, cv.speed, cv.traits, `Preview: ${cv.label}.`);
      } else {
        await ai.playVoicePreview(activeVoice, speechSpeed, "", `Preview: ${activeVoice}.`);
      }
    } catch (e: any) {
      showError(e?.message || "Preview failed.");
    } finally {
      setStatus(AppStatus.IDLE);
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
      fileName: file.name
    };

    setAssets(prev => [newAsset, ...prev]);
    if (type === 'audio') setSelectedAudioId(newAsset.id);
    else setSelectedAssetId(newAsset.id);
  };

  return (
    <div className="relative flex flex-col md:flex-row min-h-[100svh] md:h-screen bg-[var(--bg)] text-zinc-100 font-inter overflow-x-hidden overflow-y-auto md:overflow-hidden">
      <LoadingOverlay status={status} />
      {showBlueprint && <ModelMap onClose={() => setShowBlueprint(false)} />}

      {/* Mobile backdrop when the Asset Vault is open */}
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
          <i className="fa-solid fa-triangle-exclamation mr-2"></i>{errorMsg}
        </div>
      )}

      {/* Asset Vault (desktop sidebar) */}
      <aside className="hidden md:flex md:w-72 border-r border-white/5 bg-[var(--surface)] flex-col shrink-0">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-[10px] font-black uppercase tracking-widest text-violet-500">Asset Vault</h2>
            <button onClick={() => fileInputRef.current?.click()} className="w-8 h-8 bg-white/5 rounded-lg flex items-center justify-center hover:bg-violet-600 transition-all">
              <i className="fa-solid fa-plus text-[10px]"></i>
            </button>
            <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileUpload} />
          </div>

          <div className="space-y-4 max-h-[calc(100vh-100px)] overflow-y-auto scrollbar-hide">
            {assets.length === 0 && (
              <div className="p-6 border border-dashed border-white/5 rounded-2xl opacity-20 text-center">
                <i className="fa-solid fa-cloud-arrow-up text-xl mb-2"></i>
                <p className="text-[8px] uppercase font-black tracking-widest leading-relaxed">Vault Empty.<br/>Upload Media Assets.</p>
              </div>
            )}
            {assets.map(asset => (
              <AssetCard
                key={asset.id}
                asset={asset}
                isSelected={selectedAssetId === asset.id || selectedAudioId === asset.id}
                onSelect={(a) => a.type === 'audio' ? setSelectedAudioId(a.id === selectedAudioId ? null : a.id) : setSelectedAssetId(a.id === selectedAssetId ? null : a.id)}
                onDelete={(id) => setAssets(prev => prev.filter(a => a.id !== id))}
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
                  aria-label="Upload">
                  <i className="fa-solid fa-plus text-[11px]"></i>
                </button>
                <button
                  onClick={() => setVaultOpen(false)}
                  className="w-9 h-9 bg-white/5 rounded-lg flex items-center justify-center hover:bg-white/10 transition-all"
                  aria-label="Close">
                  <i className="fa-solid fa-xmark text-[12px]"></i>
                </button>
              </div>
              <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileUpload} />
            </div>

            <div className="space-y-3 max-h-[calc(100svh-110px)] overflow-y-auto scrollbar-hide pr-1">
              {assets.length === 0 && (
                <div className="p-6 border border-dashed border-white/5 rounded-2xl opacity-20 text-center">
                  <i className="fa-solid fa-cloud-arrow-up text-xl mb-2"></i>
                  <p className="text-[8px] uppercase font-black tracking-widest leading-relaxed">Vault Empty.<br/>Upload Media Assets.</p>
                </div>
              )}
              {assets.map(asset => (
                <AssetCard
                  key={asset.id}
                  asset={asset}
                  isSelected={selectedAssetId === asset.id || selectedAudioId === asset.id}
                  onSelect={(a) => {
                    if (a.type === 'audio') setSelectedAudioId(a.id === selectedAudioId ? null : a.id);
                    else setSelectedAssetId(a.id === selectedAssetId ? null : a.id);
                    setVaultOpen(false);
                  }}
                  onDelete={(id) => setAssets(prev => prev.filter(a => a.id !== id))}
                />
              ))}
            </div>
          </div>
        </aside>
      )}

      <main className="flex flex-col min-w-0 flex-none md:flex-1">
        <header className="h-14 px-4 md:px-6 flex items-center justify-between border-b border-white/5 bg-[var(--surface)]">
          <div className="flex items-center gap-3">
            <button
              className="md:hidden w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/10 transition-all"
              onClick={() => setVaultOpen(true)}
              aria-label="Open Asset Vault"
            >
              <i className="fa-solid fa-bars"></i>
            </button>

            <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${isExtensionMode ? 'bg-emerald-600 shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'bg-violet-600'}`}>
              <i className={`fa-solid ${isExtensionMode ? 'fa-forward-step' : 'fa-clapperboard'} text-white text-[10px]`}></i>
            </div>

            <span className="text-[10px] font-black uppercase tracking-[0.3em]">VisionDirector Elite</span>
          </div>

          <div className="flex items-center gap-4">
            <button onClick={() => setShowBlueprint(true)} className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-zinc-500 hover:text-white transition-all">
              <i className="fa-solid fa-share-nodes"></i>
            </button>
          </div>
        </header>

        {/* Mobile: cap monitor height so the controls remain reachable below */}
        <div className="bg-[var(--surface)] flex flex-col items-center justify-center p-4 md:p-8 overflow-hidden relative flex-none md:flex-1 h-[52svh] sm:h-[56svh] md:h-auto">

          <div style={{ aspectRatio: aspectRatio.replace(':', '/') }} className="w-full max-w-4xl bg-[var(--panel)] rounded-3xl shadow-2xl ring-1 ring-white/10 overflow-hidden flex items-center justify-center relative group">
            {activeAsset ? (
              activeAsset.type === 'video'
                ? <video src={activeAsset.url} className="w-full h-full object-contain" autoPlay loop controls />
                : <img src={activeAsset.url} className="w-full h-full object-contain" />
            ) : (
              <div className="flex flex-col items-center gap-4 opacity-10">
                <i className="fa-solid fa-film text-6xl"></i>
                <span className="text-[10px] font-black uppercase tracking-[1em]">Monitor Offline</span>
              </div>
            )}
          </div>
        </div>

        <div className="p-4 md:p-8 border-t border-white/5 bg-[var(--panel)] overflow-y-auto md:overflow-visible">
          <div className="max-w-6xl mx-auto">
            <div className="flex flex-col md:flex-row gap-4 md:gap-6 mb-6 md:mb-8">
              <div className="flex-1 space-y-3">
                <div className="flex justify-between items-center px-1">
                  <div className="flex items-center gap-3">
                    <span className="text-[9px] font-black uppercase tracking-widest text-zinc-400">
                      {isExtensionMode ? "Extension Script" : "Sequence Narrative"}
                    </span>
                    {activeAudio && (
                      <span className="text-[7px] font-black bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-full uppercase tracking-tighter border border-emerald-500/20">
                        DNA Overriding Prebuilt Voice
                      </span>
                    )}
                  </div>

                  {/* Desktop controls */}
                  <div className="hidden sm:flex flex-wrap justify-end gap-3 md:gap-4">
                    <div className="flex flex-col gap-1">
                      <div className="flex flex-col gap-1">
                        <span className="text-[7px] font-black text-zinc-500 uppercase">Supplier</span>
                        <select
                          value={supplier}
                          onChange={(e) => setSupplier(e.target.value as Supplier)}
                          className="bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-sky-400 outline-none"
                        >
                          {SUPPLIERS.map(p => (
                            <option key={p.id} value={p.id}>{p.uiLabel}</option>
                          ))}
                        </select>
                      </div>
                      <span className="text-[7px] font-black text-zinc-500 uppercase">Aspect</span>
                      <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value as AspectRatio)} className="bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-emerald-400 outline-none">
                        <option value="9:16">9:16 PORTRAIT</option><option value="16:9">16:9 LANDSCAPE</option><option value="1:1">1:1 SQUARE</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-[7px] font-black text-zinc-500 uppercase">Speed</span>
                      <select value={speechSpeed} onChange={(e) => setSpeechSpeed(e.target.value as SpeechSpeed)} className="bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-amber-400 outline-none">
                        <option value="slower">SLOWER</option>
                        <option value="slow">SLOW</option>
                        <option value="natural">NATURAL</option>
                        <option value="fast">FAST</option>
                        <option value="faster">FASTER</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-[7px] font-black text-zinc-500 uppercase">Sentiment</span>
                      <select value={sentiment} onChange={(e) => setSentiment(e.target.value as Sentiment)} className="bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-violet-400 outline-none">
                        {['neutral','cinematic','aggressive','whispering','joyful','somber'].map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Mobile controls row */}
                <div className="sm:hidden flex flex-wrap gap-3 px-1">
                  <select
                    value={supplier}
                    onChange={(e) => setSupplier(e.target.value as Supplier)}
                    className="flex-1 min-w-[110px] bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-sky-400 outline-none"
                  >
                    {SUPPLIERS.map(p => (
                      <option key={p.id} value={p.id}>{p.uiLabel}</option>
                    ))}
                  </select>
                  <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value as AspectRatio)} className="flex-1 min-w-[110px] bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-emerald-400 outline-none">
                    <option value="9:16">9:16</option><option value="16:9">16:9</option><option value="1:1">1:1</option>
                  </select>
                  <select value={speechSpeed} onChange={(e) => setSpeechSpeed(e.target.value as SpeechSpeed)} className="flex-1 min-w-[110px] bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-amber-400 outline-none">
                    <option value="slower">SLOWER</option>
                    <option value="slow">SLOW</option>
                    <option value="natural">NATURAL</option>
                    <option value="fast">FAST</option>
                    <option value="faster">FASTER</option>
                  </select>
                  <select value={sentiment} onChange={(e) => setSentiment(e.target.value as Sentiment)} className="flex-1 min-w-[110px] bg-white/5 text-[9px] font-black uppercase px-3 py-2 rounded-xl border border-white/10 text-violet-400 outline-none">
                    {['neutral','cinematic','aggressive','whispering','joyful','somber'].map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}
                  </select>
                </div>

                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className={`w-full h-28 md:h-24 bg-white/5 rounded-2xl p-4 md:p-6 text-sm font-medium border focus:border-violet-500/50 outline-none transition-all resize-none shadow-inner ${isExtensionMode ? 'border-emerald-500/30' : 'border-white/5'}`}
                  placeholder={isExtensionMode ? 'Describe the next sequence of actions precisely...' : '[Shot Type] Subject details... "Narration goes here"'}
                />
              </div>

              <div className="w-full md:w-64 flex flex-col justify-end">
                <button
                  onClick={handleExecuteRender}
                  disabled={status !== AppStatus.IDLE}
                  className={`w-full h-16 md:h-24 rounded-2xl flex flex-col items-center justify-center gap-2 transition-all shadow-2xl disabled:opacity-20 text-white font-black uppercase tracking-widest text-[10px] ${isExtensionMode ? 'bg-emerald-600 hover:bg-emerald-500 shadow-[0_10px_30px_rgba(16,185,129,0.3)]' : 'bg-violet-600 hover:bg-violet-500 shadow-[0_10px_30px_rgba(139,92,246,0.3)]'}`}
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
                  {customVoices.map(cv => (
                    <button key={cv.id} onClick={() => { setActiveCustomVoiceId(cv.id); setActiveVoice(cv.baseVoice); setSpeechSpeed(cv.speed); if(cv.sentiment) setSentiment(cv.sentiment); }} className={`px-4 py-2 rounded-xl text-[9px] font-black tracking-widest flex items-center gap-2 shrink-0 transition-all ${activeCustomVoiceId === cv.id ? 'bg-emerald-600 text-white shadow-lg' : 'bg-white/5 text-emerald-500/60 hover:bg-white/10'}`}>
                      <i className="fa-solid fa-fingerprint"></i>{cv.label}
                    </button>
                  ))}
                  <div className="w-[1px] h-6 bg-white/10 shrink-0 mx-2"></div>
                  {DEFAULT_VOICES.map(v => (
                    <button key={v.id} onClick={() => { setActiveCustomVoiceId(null); setActiveVoice(v.id); }} className={`px-4 py-2 rounded-xl text-[9px] font-black tracking-widest shrink-0 transition-all ${activeVoice === v.id && !activeCustomVoiceId && !activeAudio ? 'bg-violet-600 text-white shadow-lg' : 'bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10'} ${activeAudio ? 'opacity-20 grayscale pointer-events-none' : ''}`}>{v.label}</button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 shrink-0">
                <button
                  onClick={handlePreviewVoice}
                  disabled={status !== AppStatus.IDLE || !!activeAudio}
                  className="px-6 py-2 rounded-xl border border-white/5 text-[9px] font-black uppercase text-zinc-500 hover:text-violet-300 transition-all bg-white/[0.02] hover:bg-violet-500/5 hover:border-violet-500/20 disabled:opacity-20 disabled:pointer-events-none"
                >
                  <i className="fa-solid fa-volume-high mr-2"></i>Preview Voice
                </button>

                <button
                  onClick={handleSaveIdentity}
                  disabled={status !== AppStatus.IDLE || !activeAudio}
                  className="px-6 py-2 rounded-xl border border-white/5 text-[9px] font-black uppercase text-zinc-500 hover:text-emerald-400 transition-all bg-white/[0.02] hover:bg-emerald-500/5 hover:border-emerald-500/20 disabled:opacity-20 disabled:pointer-events-none"
                >
                  Capture Identity
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Studio;
