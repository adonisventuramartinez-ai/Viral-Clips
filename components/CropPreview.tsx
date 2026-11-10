"use client";
import { useRef, useState } from "react";

export default function CropPreview({ videoUrl, onCropChange }: { videoUrl: string, onCropChange: (crop: any) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [crop, setCrop] = useState({ x: 10, y: 10, w: 80, h: 60 }); // Porcentajes
  const [isDragging, setIsDragging] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    setStartPos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !containerRef.current) return;
    
    const dx = e.clientX - startPos.x;
    const dy = e.clientY - startPos.y;
    const rect = containerRef.current.getBoundingClientRect();
    
    // Convertir el movimiento en píxeles a porcentajes
    const dxPct = (dx / rect.width) * 100;
    const dyPct = (dy / rect.height) * 100;

    const newCrop = {
      x: Math.max(0, Math.min(100 - crop.w, crop.x + dxPct)),
      y: Math.max(0, Math.min(100 - crop.h, crop.y + dyPct)),
      w: crop.w,
      h: crop.h
    };
    
    setCrop(newCrop);
    onCropChange(newCrop);
    setStartPos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseUp = () => setIsDragging(false);

  return (
    <div 
      ref={containerRef}
      style={{ position: "relative", width: "100%", maxWidth: 600, margin: "0 auto", userSelect: "none" }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <video src={videoUrl} controls style={{ width: "100%", display: "block" }} />
      
      {/* Overlay Oscuro */}
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", pointerEvents: "none" }} />
      
      {/* Recuadro de Recorte */}
      <div
        style={{
          position: "absolute",
          left: `${crop.x}%`, top: `${crop.y}%`,
          width: `${crop.w}%`, height: `${crop.h}%`,
          border: "2px solid #2ee6d6",
          boxShadow: "0 0 0 9999px rgba(0,0,0,0.3)",
          cursor: "move",
          background: "transparent",
          pointerEvents: "auto"
        }}
        onMouseDown={handleMouseDown}
      >
        <div style={{ position: "absolute", bottom: 0, right: 0, width: 20, height: 20, background: "#2ee6d6", cursor: "se-resize" }} />
      </div>
    </div>
  );
}
