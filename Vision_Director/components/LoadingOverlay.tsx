
import React from 'react';
import { AppStatus } from '../types';

interface LoadingOverlayProps {
  status: AppStatus;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({ status }) => {
  if (status === AppStatus.IDLE || status === AppStatus.ERROR) return null;

  let messages = ["Processing..."];
  let title = "Working";
  let icon = "fa-spinner";

  if (status === AppStatus.GENERATING_VIDEO) {
    messages = ["Analyzing narrative flow...", "Ensuring character consistency...", "Simulating temporal motion...", "Finalizing rendering..."];
    title = "Generating Cinematic Video";
    icon = "fa-film";
  } else if (status === AppStatus.EXTENDING_VIDEO) {
    messages = ["Fetching temporal reference...", "Maintaining subject consistency...", "Generating subsequent frames...", "Stitching sequence..."];
    title = "Extending Cinematic Sequence";
    icon = "fa-forward-step";
  } else if (status === AppStatus.GENERATING_IMAGE) {
    messages = ["Synthesizing imagery...", "Applying lighting pass...", "Enhancing details...", "Finalizing image..."];
    title = "Creating AI Visuals";
    icon = "fa-wand-magic-sparkles";
  } else if (status === AppStatus.GENERATING_AUDIO) {
    messages = ["Analyzing vocal characteristics...", "Applying sentiment profile...", "Cleaning audio stream...", "Finalizing track..."];
    title = "Synthesizing Narration";
    icon = "fa-volume-up";
  }

  const [messageIdx, setMessageIdx] = React.useState(0);

  React.useEffect(() => {
    const interval = setInterval(() => {
      setMessageIdx(prev => (prev + 1) % messages.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [messages.length]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-zinc-950/90 backdrop-blur-xl">
      <div className="relative mb-12 scale-125">
        <div className="w-24 h-24 border-4 border-violet-500/10 rounded-full animate-ping absolute inset-0"></div>
        <div className="w-24 h-24 border-4 border-t-violet-500 border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin"></div>
        <div className="absolute inset-0 flex items-center justify-center">
          <i className={`fas ${icon} text-3xl text-violet-500`}></i>
        </div>
      </div>
      <h3 className="text-2xl font-black text-white mb-3 tracking-tighter uppercase">{title}</h3>
      <p className="text-zinc-500 text-[11px] font-bold uppercase tracking-[0.3em] animate-pulse">{messages[messageIdx]}</p>
    </div>
  );
};
