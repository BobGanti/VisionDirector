import React, { useState, useEffect } from 'react';
import Studio from './components/Studio';
import { ModelMap } from './components/ModelMap';
import ErrorBoundary from "./components/ErrorBoundary";

const App: React.FC = () => {
  const [hasKey, setHasKey] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isBridgeMode, setIsBridgeMode] = useState(false);
  const [showBlueprint, setShowBlueprint] = useState(false);

  useEffect(() => {
    const check = async () => {
      // 1) Manual override keys (localStorage)
      const manualGeminiKey = localStorage.getItem('vision_api_key_override');
      const manualOpenAIKey = localStorage.getItem('vision_openai_api_key_override');

      if (
        (manualGeminiKey && manualGeminiKey.length > 5) ||
        (manualOpenAIKey && manualOpenAIKey.length > 5)
      ) {
        setHasKey(true);
        setIsLoading(false);
        return;
      }

      // 2) AI Studio Bridge
      const bridge = (window as any).aistudio;
      if (bridge) {
        setIsBridgeMode(true);
        try {
          const selected = await bridge.hasSelectedApiKey();
          if (selected) setHasKey(true);
        } catch (e) {}
      }

      // 3) Server-injected keys (browser shim)
      const injectedGeminiKey = (window as any)?.process?.env?.API_KEY;
      const injectedOpenAIKey = (window as any)?.process?.env?.OPENAI_API_KEY;

      if (
        (injectedGeminiKey && injectedGeminiKey !== "undefined" && injectedGeminiKey.length > 5) ||
        (injectedOpenAIKey && injectedOpenAIKey !== "undefined" && injectedOpenAIKey.length > 5)
      ) {
        setHasKey(true);
      }

      setIsLoading(false);
    };

    check();
    const timer = setTimeout(check, 1000);
    return () => clearTimeout(timer);
  }, []);

  const handleSelectKey = async () => {
    const bridge = (window as any).aistudio;
    if (bridge) {
      await bridge.openSelectKey();
      setHasKey(true);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#020202]">
        <div className="w-10 h-10 border-2 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  // Lock screen (now also allows opening Model Blueprint to paste keys)
  if (!hasKey && !isBridgeMode) {
    return (
      <div className="min-h-screen bg-[#020202] flex flex-col items-center justify-center p-6 text-center">
        {showBlueprint && <ModelMap onClose={() => setShowBlueprint(false)} />}

        <div className="max-w-md w-full space-y-8 animate-in fade-in zoom-in-95 duration-700">
          <div className="w-20 h-20 bg-violet-600/10 rounded-3xl mx-auto flex items-center justify-center border border-violet-500/20">
            <i className="fa-solid fa-lock text-3xl text-violet-500"></i>
          </div>

          <div className="space-y-2">
            <h1 className="text-3xl font-black text-white uppercase tracking-tighter">Production Locked</h1>
            <p className="text-zinc-500 text-sm font-medium uppercase tracking-widest px-8 leading-relaxed">
              VisionDirector Elite requires an API Key (Google or OpenAI) for rendering services.
            </p>
          </div>

          <div className="pt-4 space-y-4">
            <button
              onClick={() => window.location.reload()}
              className="w-full h-14 bg-white text-black font-black uppercase tracking-widest text-[11px] rounded-2xl hover:scale-[1.02] transition-all active:scale-95"
            >
              Check Environment Again
            </button>

            <button
              onClick={() => setShowBlueprint(true)}
              className="w-full h-14 bg-white/5 border border-white/10 text-white font-black uppercase tracking-widest text-[11px] rounded-2xl hover:bg-white/10 transition-all active:scale-95"
            >
              Open Model Blueprint
            </button>

            <p className="text-[9px] text-zinc-600 font-black uppercase tracking-[0.2em]">
              Or paste your key(s) in the <span className="text-violet-400">Model Blueprint</span>.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ...inside your component:
  return (
    <ErrorBoundary>
      <Studio isBridgeMode={isBridgeMode || !!(window as any).aistudio} />
    </ErrorBoundary>
  );

};

export default App;
