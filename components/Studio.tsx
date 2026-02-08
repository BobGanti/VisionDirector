import React, { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, FC } from 'react';

import type {
  MediaAsset,
  VoiceProfile,
  AspectRatio,
  CustomVoice,
  SpeechSpeed,
  Sentiment,
  ParsedScript,
} from '../types';
import { AppStatus } from '../types';

import { GeminiService } from '../services/geminiService';
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
  { id: 'Aoide', label: 'AOIDE' },
  { id: 'Orion', label: 'ORION' },
];

type StudioProps = { isBridgeMode?: boolean };

function safeJsonArray<T>(raw: string | null): T[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function visualsToPrompt(visuals: ParsedScript['visuals'], fallback: string): string {
  // Be defensive: some parsers output a string, others output arrays.
  if (!visuals) return fallback;
  if (Array.isArray(visuals)) return visuals.filter(Boolean).join('\n');
  if (typeof visuals === 'string') return visuals;
  return fallback;
}

const Studio: FC<StudioProps> = ({ isBridgeMode = false }) => {
  const [assets, setAssets] = useState<MediaAsset[]>(() =>
    safeJsonArray<MediaAsset>(localStorage.getItem('vision_studio_assets_v23'))
  );

  const [customVoices, setCustomVoices] = useState<CustomVoice[]>(() =>
    safeJsonArray<CustomVoice>(localStorage.getItem('vision_studio_voices_v23'))
  );

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

  const activeAsset = assets.find((a) => a.id === selectedAssetId) || null;
  const activeAudio = assets.find((a) => a.type === 'audio' && a.id === selectedAudioId) || null;
  const isExtensionMode = activeAsset?.type === 'video' && !!activeAsset.videoRef;

  useEffect(() => {
    localStorage.setItem('vision_studio_assets_v23', JSON.stringify(assets));
  }, [assets]);

  useEffect(() => {
    localStorage.setItem('vision_studio_voices_v23', JSON.stringify(customVoices));
  }, [customVoices]);

  const showError = (msg: string) => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 8000);
  };

  const handleExecuteRender = async () => {
    try {
      setStatus(isExtensionMode ? AppStatus.EXTENDING_VIDEO : AppStatus.ANALYZING_SCRIPT);

      const script = await GeminiService.parseScript(prompt);

      let img1: MediaAsset | null = activeAsset?.type === 'image' ? activeAsset : null;
      const extensionRef = isExtensionMode ? activeAsset?.videoRef ?? null : null;

      // If no image, no audio, no extension ref, and user provided text, generate an image reference
      if (!img1 && !activeAudio && !extensionRef && prompt) {
        setStatus(AppStatus.GENERATING_IMAGE);
        const imgPrompt = visualsToPrompt(script.visuals, prompt);
        const genImg = await GeminiService.generateImage(imgPrompt, aspectRatio);

        if (genImg) {
          const newAsset: MediaAsset = {
            id: `gen-${Date.now()}`,
            type: 'image',
            url: genImg,
            timestamp: Date.now(),
            fileName: 'GEN_REF.png',
          };
          setAssets((prev) => [newAsset, ...prev]);
          img1 = newAsset;
        }
      }

      let voiceTraits = '';

      // DNA mode: if audio selected, analyse voice and ensure narration exists
      if (activeAudio) {
        setStatus(AppStatus.GENERATING_AUDIO);
        voiceTraits = await GeminiService.analyzeVoice(activeAudio.url, sentiment);

        if (!script.narration) {
          script.narration = await GeminiService.transcribeAudio(activeAudio.url);
        }
      } else if (activeCustomVoiceId) {
        voiceTraits = customVoices.find((v) => v.id === activeCustomVoiceId)?.traits || '';
      }

      setStatus(AppStatus.GENERATING_VIDEO);

      const videoResult = await GeminiService.generateVideo(
        visualsToPrompt(script.visuals, prompt),
        script.narration || '',
        aspectRatio,
        img1?.url,
        voiceTraits,
        activeVoice,
        speechSpeed,
        sentiment,
        extensionRef
      );

      if (videoResult) {
        const vidAsset: MediaAsset = {
          id: `vid-${Date.now()}`,
          type: 'video',
          url: videoResult.url,
          videoRef: videoResult.videoRef,
          timestamp: Date.now(),
          fileName: isExtensionMode ? 'EXT_SEQ.mp4' : 'FINAL.mp4',
        };

        setAssets((prev) => [vidAsset, ...prev]);
        setSelectedAssetId(vidAsset.id);
      }
    } catch (e: any) {
      showError(e?.message || 'Render failed.');
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
      const traits = await GeminiService.analyzeVoice(activeAudio.url, sentiment);

      const newVoice: CustomVoice = {
        id: `v-${Date.now()}`,
        label: label.toUpperCase(),
        baseVoice: activeVoice,
        traits,
        speed: speechSpeed,
        sentiment,
      };

      setCustomVoices((prev) => [newVoice, ...prev]);
      setActiveCustomVoiceId(newVoice.id);

      await GeminiService.playVoicePreview(
        newVoice.baseVoice,
        newVoice.speed,
        newVoice.traits,
        'Identity Captured.'
      );
    } catch (e: any) {
      showError(e?.message || 'Cloning failed.');
    } finally {
      setStatus(AppStatus.IDLE);
    }
  };

  const handlePreviewVoice = async () => {
    // Prebuilt voice preview without uploading audio
    if (status !== AppStatus.IDLE) return;

    // If DNA audio is selected, prebuilt voice is disabled by design
    if (activeAudio) return showError('UNSELECT DNA AUDIO TO PREVIEW PREBUILT VOICES.');

    setStatus(AppStatus.GENERATING_AUDIO);

    try {
      if (activeCustomVoiceId) {
        const cv = customVoices.find((v) => v.id === activeCustomVoiceId);
        if (!cv) throw new Error('VOICE_PROFILE_NOT_FOUND');

        await GeminiService.playVoicePreview(cv.baseVoice, cv.speed, cv.traits, `Preview: ${cv.label}.`);
      } else {
        await GeminiService.playVoicePreview(activeVoice, speechSpeed, '', `Preview: ${activeVoice}.`);
      }
    } catch (e: any) {
      showError(e?.message || 'Preview failed.');
    } finally {
      setStatus(AppStatus.IDLE);
    }
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const base64 = await blobToBase64(file);
    const type = file.type.startsWith('image')
      ? 'image'
      : file.type.startsWith('video')
      ? 'video'
      : 'audio';

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

  return (
    <div className="flex h-screen bg-[#020202] text-zinc-100 overflow-hidden font-inter">
      <LoadingOverlay status={status} />
      {showBlueprint && <ModelMap onClose={() => setShowBlueprint(false)} />}

      {errorMsg && (
        <div className="fixed top-10 left-1/2 -translate-x-1/2 z-[200] bg-red-600 px-6 py-3 rounded-xl shadow-2xl font-black uppercase text-[10px] tracking-widest">
          <i className="fa-solid fa-triangle-exclamation mr-2"></i>
          {errorMsg}
        </div>
      )}

      <aside className="w-72 border-r border-white/5 bg-[#050505] flex flex-col shrink-0">
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

      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-14 px-6 flex items-center justify-between border-b border-white/5 bg-black">
          <div className="flex items-center gap-3">
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${
                isExtensionMode
                  ? 'bg-emerald-600 shadow-[0_0_15px_rgba(16,185,129,0.3)]'
                  : 'bg-violet-600'
              }`}
            >
              <i
                className={`fa-solid ${isExtensionMode ? 'fa-forward-step' : 'fa-clapperboard'} text-white text-[10px]`}
              ></i>
            </div>
            <span className="text-[10px] font-black uppercase tracking-[0.3em]">VisionDirector Elite</span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowBlueprint(true)}
              className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-zinc-500 hover:text-white transition-all"
            >
              <i className="fa-solid fa-share-nodes"></i>
            </button>
          </div>
        </header>

        <div className="flex-1 bg-black flex flex-col items-center justify-center p-8 overflow-hidden relative">
          <div
            style={{ aspectRatio: aspectRatio.replace(':', '/') }}
            className="w-full max-w-4xl bg-[#0a0a0c] rounded-3xl shadow-2xl ring-1 ring-white/10 overflow-hidden flex items-center justify-center relative group"
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

            {isExtensionMode && (
              <div className="absolute top-6 left-6 flex flex-col gap-2">
                <div className="bg-emerald-500 text-white text-[9px] font-black px-4 py-1.5 rounded-full uppercase tracking-widest shadow-2xl animate-pulse">
                  Director Protocol: Extension Mode
                </div>

                <div className="bg-black/80 backdrop-blur-md border border-emerald-500/30 p-4 rounded-2xl max-w-xs animate-in slide-in-from-left-4 duration-500">
                  <p className="text-[8px] font-black text-emerald-400 uppercase tracking-widest mb-2 border-b border-emerald-500/20 pb-1">
                    Operational Hints
                  </p>
                  <ul className="text-[9px] text-zinc-300 space-y-1 font-medium">
                    <li>• Keep character names identical.</li>
                    <li>• Describe action starting from last frame.</li>
                    <li>• Maintaining DNA: Voice signature persistent.</li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="p-8 border-t border-white/5 bg-[#080808]">
          <div className="max-w-6xl mx-auto">
            <div className="flex gap-6 mb-8">
              <div className="flex-1 space-y-3">
                <div className="flex justify-between items-center px-1">
                  <div className="flex items-center gap-3">
                    <span className="text-[9px] font-black uppercase tracking-widest text-zinc-600">
                      {isExtensionMode ? 'Extension Script' : 'Sequence Narrative'}
                    </span>

                    {activeAudio && (
                      <span className="text-[7px] font-black bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-full uppercase tracking-tighter border border-emerald-500/20">
                        DNA Overriding Prebuilt Voice
                      </span>
                    )}
                  </div>

                  <div className="flex gap-4">
                    <div className="flex flex-col gap-1">
                      <span className="text-[7px] font-black text-zinc-500 uppercase">Aspect</span>
                      <select
                        value={aspectRatio}
                        onChange={(e) => setAspectRatio(e.target.value as AspectRatio)}
                        className="bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-emerald-400 outline-none"
                      >
                        <option value="9:16">9:16 PORTRAIT</option>
                        <option value="16:9">16:9 LANDSCAPE</option>
                        <option value="1:1">1:1 SQUARE</option>
                      </select>
                    </div>

                    <div className="flex flex-col gap-1">
                      <span className="text-[7px] font-black text-zinc-500 uppercase">Speed</span>
                      <select
                        value={speechSpeed}
                        onChange={(e) => setSpeechSpeed(e.target.value as SpeechSpeed)}
                        className="bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-amber-400 outline-none"
                      >
                        <option value="slower">SLOWER</option>
                        <option value="slow">SLOW</option>
                        <option value="natural">NATURAL</option>
                        <option value="fast">FAST</option>
                        <option value="faster">FASTER</option>
                      </select>
                    </div>

                    <div className="flex flex-col gap-1">
                      <span className="text-[7px] font-black text-zinc-500 uppercase">Sentiment</span>
                      <select
                        value={sentiment}
                        onChange={(e) => setSentiment(e.target.value as Sentiment)}
                        className="bg-white/5 text-[9px] font-black uppercase px-3 py-1.5 rounded-xl border border-white/10 text-violet-400 outline-none"
                      >
                        {['neutral', 'cinematic', 'aggressive', 'whispering', 'joyful', 'somber'].map((s) => (
                          <option key={s} value={s}>
                            {s.toUpperCase()}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className={`w-full h-24 bg-white/5 rounded-2xl p-6 text-sm font-medium border focus:border-violet-500/50 outline-none transition-all resize-none shadow-inner ${
                    isExtensionMode ? 'border-emerald-500/30' : 'border-white/5'
                  }`}
                  placeholder={
                    isExtensionMode
                      ? 'Describe the next sequence of actions precisely...'
                      : '[Shot Type] Subject details... "Narration goes here"'
                  }
                />
              </div>

              <div className="w-64 flex flex-col justify-end">
                <button
                  onClick={handleExecuteRender}
                  disabled={status !== AppStatus.IDLE}
                  className={`w-full h-24 rounded-2xl flex flex-col items-center justify-center gap-2 transition-all shadow-2xl disabled:opacity-20 text-white font-black uppercase tracking-widest text-[10px] ${
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

            <div className="flex items-center justify-between border-t border-white/5 pt-6">
              <div className="flex items-center gap-6 overflow-hidden flex-1">
                <div className="shrink-0 flex flex-col">
                  <span className="text-[9px] font-black uppercase text-zinc-600 tracking-widest">Identity Vault</span>
                  <span className="text-[7px] text-zinc-700 font-bold uppercase">
                    {activeAudio ? 'DNA ACTIVE' : 'PREBUILT'}
                  </span>
                </div>

                <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide pr-8">
                  {customVoices.map((cv) => (
                    <button
                      key={cv.id}
                      onClick={() => {
                        setActiveCustomVoiceId(cv.id);
                        setActiveVoice(cv.baseVoice);
                        setSpeechSpeed(cv.speed);
                        if (cv.sentiment) setSentiment(cv.sentiment);
                      }}
                      className={`px-4 py-2 rounded-xl text-[9px] font-black tracking-widest flex items-center gap-2 shrink-0 transition-all ${
                        activeCustomVoiceId === cv.id
                          ? 'bg-emerald-600 text-white shadow-lg'
                          : 'bg-white/5 text-emerald-500/60 hover:bg-white/10'
                      }`}
                    >
                      <i className="fa-solid fa-fingerprint"></i>
                      {cv.label}
                    </button>
                  ))}

                  <div className="w-[1px] h-6 bg-white/10 shrink-0 mx-2"></div>

                  {DEFAULT_VOICES.map((v) => (
                    <button
                      key={v.id}
                      onClick={() => {
                        setActiveCustomVoiceId(null);
                        setActiveVoice(v.id);
                      }}
                      className={`px-4 py-2 rounded-xl text-[9px] font-black tracking-widest shrink-0 transition-all ${
                        activeVoice === v.id && !activeCustomVoiceId && !activeAudio
                          ? 'bg-violet-600 text-white shadow-lg'
                          : 'bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10'
                      } ${activeAudio ? 'opacity-20 grayscale pointer-events-none' : ''}`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={handlePreviewVoice}
                  disabled={status !== AppStatus.IDLE || !!activeAudio}
                  className="px-6 py-2 rounded-xl border border-white/5 text-[9px] font-black uppercase text-zinc-500 hover:text-violet-300 transition-all bg-white/[0.02] hover:bg-violet-500/5 hover:border-violet-500/20 disabled:opacity-20 disabled:pointer-events-none"
                >
                  <i className="fa-solid fa-volume-high mr-2"></i>
                  Preview Voice
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
