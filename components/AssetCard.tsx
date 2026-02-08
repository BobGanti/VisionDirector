
import React from 'react';
import { MediaAsset } from '../types';

interface AssetCardProps {
  asset: MediaAsset;
  onSelect: (asset: MediaAsset) => void;
  onDelete: (id: string) => void;
  isSelected?: boolean;
}

export const AssetCard: React.FC<AssetCardProps> = ({ asset, onSelect, onDelete, isSelected }) => {
  const handleAction = (e: React.MouseEvent, action: () => void) => {
    e.preventDefault();
    e.stopPropagation();
    action();
  };

  const renderPreview = () => {
    switch (asset.type) {
      case 'video':
        return <video src={asset.url} className="w-full h-full object-cover" muted />;
      case 'audio':
        return (
          <div className="w-full h-full flex flex-col items-center justify-center bg-violet-600/5">
            <i className="fa-solid fa-volume-high text-violet-500 text-sm mb-1"></i>
            <span className="text-[8px] font-black text-violet-500/50 uppercase tracking-widest">Voice ID</span>
          </div>
        );
      default:
        return <img src={asset.url} alt={asset.fileName} className="w-full h-full object-cover" />;
    }
  };

  return (
    <div 
      onClick={() => onSelect(asset)}
      className={`group relative cursor-pointer overflow-hidden rounded-xl border transition-all active:scale-[0.97] ${
        isSelected 
        ? 'border-violet-500 bg-violet-500/10 shadow-lg ring-1 ring-violet-500/30' 
        : 'border-white/5 bg-white/[0.02] hover:border-white/10'
      }`}
    >
      <div className="aspect-[4/3] relative overflow-hidden bg-black/40">
        {renderPreview()}
        
        {isSelected && asset.type !== 'audio' && (
          <div className="absolute top-2 left-2 bg-violet-600 text-white text-[8px] font-black px-2 py-1 rounded shadow-lg uppercase tracking-widest animate-in zoom-in-50 duration-200">
            Reference Frame
          </div>
        )}

        <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
           <button onClick={(e) => handleAction(e, () => onDelete(asset.id))} className="w-6 h-6 rounded-md bg-red-600/90 hover:bg-red-600 text-white flex items-center justify-center">
             <i className="fa-solid fa-trash text-[8px]"></i>
           </button>
        </div>

        <div className="absolute bottom-0 inset-x-0 p-2 bg-gradient-to-t from-black/80 to-transparent">
           <p className="text-[8px] text-zinc-400 font-bold truncate opacity-80 uppercase tracking-tighter">{asset.fileName}</p>
        </div>
      </div>
    </div>
  );
};
