// apps/mealshopper-web/src/components/DealImageTooltip.tsx
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface DealImageTooltipProps {
  imageUrl?: string | null;
  itemName: string;
}

export const DealImageTooltip: React.FC<DealImageTooltipProps> = ({ imageUrl, itemName }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Calculate position relative to viewport so it floats completely outside all parent divs
  const handleMouseEnter = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setTooltipPos({
        top: Math.max(16, rect.top + rect.height / 2 - 130), // Center vertically relative to button
        left: rect.left - 270, // 256px width + 14px gutter
      });
      setIsHovered(true);
    }
  };

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsModalOpen(false);
    };
    if (isModalOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isModalOpen]);

  if (!imageUrl) {
    return <span className="text-xs text-stone-400 italic">No image</span>;
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setIsHovered(false)}
        onClick={(e) => {
          e.stopPropagation();
          setIsHovered(false);
          setIsModalOpen(true);
        }}
        className="text-xs font-semibold text-[#1E7538] hover:text-[#14532d] underline focus:outline-none cursor-pointer"
      >
        View Image
      </button>

      {/* 1. FLOATING HOVER PREVIEW (PORTALED TO BODY TO PREVENT OVERFLOW CLIPPING) */}
      {isHovered &&
        !isModalOpen &&
        createPortal(
          <div
            style={{ top: `${tooltipPos.top}px`, left: `${tooltipPos.left}px` }}
            className="fixed z-[9999] w-64 rounded-xl border border-stone-200 bg-white p-2.5 shadow-2xl pointer-events-none transition-all duration-150 animate-in fade-in zoom-in-95"
          >
            <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-stone-50 flex items-center justify-center p-2">
              <img
                src={imageUrl}
                alt={itemName}
                className="max-h-full max-w-full object-contain"
                loading="eager"
              />
            </div>
            <p className="mt-2 text-xs font-semibold text-stone-800 line-clamp-1">{itemName}</p>
            <p className="text-[10px] text-stone-400 italic">Click link to zoom 2x</p>
          </div>,
          document.body
        )}

      {/* 2. FULL-SCREEN 2X BLOWN-UP MODAL */}
      {isModalOpen &&
        createPortal(
          <div
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-stone-900/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
            onClick={(e) => {
              e.stopPropagation();
              setIsModalOpen(false);
            }}
          >
            <div
              className="relative max-w-3xl w-full rounded-2xl bg-white p-6 shadow-2xl border border-stone-200"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Close Button */}
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="absolute top-4 right-4 h-8 w-8 rounded-full bg-stone-100 hover:bg-stone-200 text-stone-600 flex items-center justify-center font-bold text-lg transition"
                title="Close"
              >
                &times;
              </button>

              <div className="mb-3 pr-8">
                <h3 className="text-base font-bold text-stone-900">{itemName}</h3>
                <span className="text-xs text-stone-500 font-medium">Circular Scan (High Resolution)</span>
              </div>

              {/* Blown-up container (up to 800px / 2x rendering) */}
              <div className="w-full flex items-center justify-center bg-stone-50 rounded-xl p-4 border border-stone-100 min-h-[320px] max-h-[75vh] overflow-auto">
                <img
                  src={imageUrl}
                  alt={itemName}
                  className="max-h-[65vh] w-auto object-contain transition-transform duration-200"
                />
              </div>

              <div className="mt-4 flex justify-between items-center text-xs text-stone-500">
                <span>Press <kbd className="px-1.5 py-0.5 bg-stone-100 border border-stone-300 rounded text-[11px] font-mono">Esc</kbd> to exit</span>
              </div>
            </div>
          </div>,
          document.body
        )}
    </>
  );
};