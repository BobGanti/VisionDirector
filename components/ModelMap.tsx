
import React, { useState } from 'react';
import { GeminiService } from '../services/geminiService';

export const ModelMap: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const mapData = GeminiService.getModelMap();
  const [apiKey, setApiKey] = useState(localStorage.getItem('vision_api_key_override') || '');
  const [isSaved, setIsSaved] = useState(false);

  const handleSaveKey = () => {
    localStorage.setItem('vision_api_key_override', apiKey);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
    // Reload to refresh App state if key was missing
    window.location.reload();
  };

  return (
    <div className="fixed inset-0 z-[300] bg-black/95 backdrop-blur-2xl flex justify-center p-4 lg:p-12 overflow-y-auto items-start py-12 lg:py-24">
      <div className="w-full max-w-6xl bg-[#0a0a0c] border border-white/10 rounded-[2rem] shadow-2xl p-8 lg:p-12 relative overflow-visible">
        <div className="absolute inset-0 opacity-5 pointer-events-none rounded-[2rem]" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '24px 24px' }}></div>
        
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
            <button onClick={onClose} className="w-12 h-12 bg-white/5 hover:bg-white/10 rounded-full flex items-center justify-center transition-all sticky top-0">
              <i className="fas fa-times"></i>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6 mb-12">
            {mapData.map((item, idx) => (
              <div key={idx} className="bg-white/[0.03] border border-white/5 p-6 rounded-2xl hover:border-violet-500/50 transition-all group">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500 group-hover:text-violet-400">{item.feature}</span>
                  <div className="px-2 py-1 bg-violet-600/10 border border-violet-500/20 rounded text-[9px] font-bold text-violet-400">NODE_{idx + 1}</div>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <p className="text-[9px] uppercase font-black text-zinc-600 mb-1">Configuration Key</p>
                    <code className="text-sm font-mono text-emerald-400 bg-emerald-500/5 px-2 py-1 rounded select-all block mb-2">{item.model}</code>
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

          {/* Secure Vault Section */}
          <div className="p-8 bg-zinc-900 border border-white/10 rounded-3xl shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <i className="fas fa-shield-halved text-6xl text-emerald-500"></i>
            </div>
            
            <div className="relative z-10">
              <div className="mb-6">
                <h3 className="text-[10px] font-black uppercase tracking-[0.4em] text-emerald-500 mb-2">Secure Vault</h3>
                <p className="text-xl font-bold text-white uppercase tracking-tight">API Interface Credentials</p>
                <p className="text-[10px] text-zinc-500 mt-1 uppercase font-medium">Override server-side variables with a custom Gemini key for persistent local access.</p>
              </div>

              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1 relative">
                  <input 
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter Gemini API Key..."
                    className="w-full bg-black/50 border border-white/10 rounded-2xl px-6 py-4 text-sm font-mono text-emerald-400 focus:border-emerald-500/50 outline-none transition-all placeholder:text-zinc-700"
                  />
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 flex gap-2">
                    <i className="fas fa-key text-[10px] text-emerald-500/30"></i>
                  </div>
                </div>
                <button 
                  onClick={handleSaveKey}
                  className={`px-8 rounded-2xl font-black uppercase tracking-widest text-[10px] transition-all flex items-center justify-center gap-3 ${isSaved ? 'bg-emerald-600 text-white' : 'bg-white/5 hover:bg-white/10 text-white'}`}
                >
                  <i className={`fas ${isSaved ? 'fa-check' : 'fa-sync'}`}></i>
                  {isSaved ? 'Vault Synced' : 'Update Key'}
                </button>
              </div>
              <div className="mt-4 flex gap-4">
                <a href="https://ai.google.dev/gemini-api/docs/billing" target="_blank" className="text-[9px] font-bold uppercase tracking-widest text-zinc-600 hover:text-white transition-colors underline decoration-zinc-800">Setup Gemini Billing</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
