"use client";
import { useRef, useState, useEffect } from "react";

export default function CropPreview({ videoUrl, onCropChange }: { videoUrl: string, onCropChange: (crop: any) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [crop, setCrop] = useState({ x: 10, y: 10, w: 80, h: 60 });
  const [isDragging, setIsDragging] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  
  // --- NUEVO: Estado para guardar el ID de YouTube ---
  const [ytId, setYtId] = useState<string | null>(null);

  // --- NUEVO: Detectar si el link es de YouTube ---
  useEffect(() => {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = videoUrl.match(regExp);
    if (match && match[2].length === 11) {
      setYtId(match[2]);
    } else {
      setYtId(null);
    }
  }, [videoUrl]);

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
      style={{ position: "relative", width: "100%", aspectRatio: "16/9", background: "#000", overflow: "hidden", userSelect: "none" }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Si es YouTube, usamos el iframe. Si no, un video normal */}
      {ytId ? (
        <iframe
          width="100%"
          height="100%"
          src={`https://www.youtube.com/embed/${ytId}?controls=1&rel=0`}
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          style={{ pointerEvents: "none" }} // Evitamos que el iframe bloquee el arrastre del recuadro
        />
      ) : (
        <video src={videoUrl} controls style={{ width: "100%", height: "100%", objectFit: "cover", pointerEvents: "none" }} />
      )}
      
      {/* Overlay Oscuro */}
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)", pointerEvents: "none" }} />
      
      {/* Recuadro de Recorte */}
      <div
        style={{
          position: "absolute",
          left: `${crop.x}%`, top: `${crop.y}%`,
          width: `${crop.w}%`, height: `${crop.h}%`,
          border: "2px solid #2ee6d6",
          boxShadow: "0 0 0 9999px rgba(0,0,0,0.2)",
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
