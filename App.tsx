
import React, { useState, useEffect } from 'react';
import Studio from './components/Studio';

const App: React.FC = () => {
  const [hasKey, setHasKey] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isBridgeMode, setIsBridgeMode] = useState(false);

  useEffect(() => {
    const check = async () => {
      // 1. Check for manual override key in localStorage
      const manualKey = localStorage.getItem('vision_api_key_override');
      if (manualKey && manualKey.length > 5) {
        setHasKey(true);
        setIsLoading(false);
        return;
      }

      // 2. Check for AI Studio Bridge
      const bridge = (window as any).aistudio;
      if (bridge) {
        setIsBridgeMode(true);
        try {
          const selected = await bridge.hasSelectedApiKey();
          if (selected) setHasKey(true);
        } catch (e) {}
      }
      
      // 3. Check for process.env (Server Injection)
      // 3. Check for server-injected key (browser shim)
      const injectedKey = (window as any)?.process?.env?.API_KEY;
      if (injectedKey && injectedKey !== "undefined" && injectedKey.length > 5) {
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

  if (isLoading) return (
    <div className="min-h-screen flex items-center justify-center bg-[#020202]">
      <div className="w-10 h-10 border-2 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  );

  // Still show lock screen if no key found anywhere
  if (!hasKey && !isBridgeMode) {
    return (
      <div className="min-h-screen bg-[#020202] flex flex-col items-center justify-center p-6 text-center">
        <div className="max-w-md w-full space-y-8 animate-in fade-in zoom-in-95 duration-700">
          <div className="w-20 h-20 bg-violet-600/10 rounded-3xl mx-auto flex items-center justify-center border border-violet-500/20">
            <i className="fa-solid fa-lock text-3xl text-violet-500"></i>
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-black text-white uppercase tracking-tighter">Production Locked</h1>
            <p className="text-zinc-500 text-sm font-medium uppercase tracking-widest px-8 leading-relaxed">
              VisionDirector Elite requires an API Key for rendering services. 
            </p>
          </div>
          
          <div className="pt-4 space-y-4">
            <button 
              onClick={() => window.location.reload()}
              className="w-full h-14 bg-white text-black font-black uppercase tracking-widest text-[11px] rounded-2xl hover:scale-[1.02] transition-all active:scale-95"
            >
              Check Environment Again
            </button>
            <p className="text-[9px] text-zinc-600 font-black uppercase tracking-[0.2em]">
              Or provide key in the <span className="text-violet-400">Model Blueprint</span> if accessible.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <Studio isBridgeMode={isBridgeMode || !!(window as any).aistudio} />;
};

export default App;
