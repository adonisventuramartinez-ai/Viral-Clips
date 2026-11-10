"use client";
import { useState } from "react";
import CropPreview from "@/components/CropPreview"; // <-- Importamos el componente

export default function Crear() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  
  // --- NUEVOS ESTADOS PARA LA VISTA PREVIA ---
  const [videoUrl, setVideoUrl] = useState("");
  const [crop, setCrop] = useState({ x: 10, y: 10, w: 80, h: 60 });
  // -------------------------------------------

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    const f = new FormData(e.currentTarget);
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "vod_url",
        url: f.get("url"),
        range_from: f.get("from"),
        range_to: f.get("to"),
        clip_seconds: Number(f.get("secs")),
        clips: Number(f.get("count")),
        quality: f.get("quality"),
        layout: f.get("layout"),
        custom_crop: crop, // <-- NUEVO: Enviamos el encuadre personalizado
      }),
    });
    const data = await res.json();
    if (res.ok && !data.demo) {
      window.location.href = "/biblioteca";
      return;
    }
    setMsg(res.ok ? { ok: true, text: data.message } : { ok: false, text: data.error });
    setBusy(false);
  }

  return (
    <>
      <h1>Crear clips</h1>
      <p className="sub">Pega un link de YouTube, Kick o Twitch (o sube un video) y la IA saca los mejores momentos.</p>
      
      <form className="card neon" onSubmit={submit}>
        <label>Link del video</label>
        <input 
          name="url" 
          placeholder="https://www.youtube.com/watch?v=..." 
          onChange={(e) => setVideoUrl(e.target.value)} // <-- Actualiza el video para la vista previa
        />
        
        {/* --- NUEVA VISTA PREVIA --- */}
        {videoUrl && videoUrl.startsWith("http") && (
          <div style={{ marginTop: 16, marginBottom: 16 }}>
            <label>Vista previa del encuadre</label>
            <CropPreview 
              videoUrl={videoUrl} 
              onCropChange={(newCrop) => setCrop(newCrop)} 
            />
            <p className="sub" style={{ fontSize: 12, marginTop: 4 }}>
              * Arrastra el recuadro para elegir qué parte del video quieres en tu clip.
            </p>
          </div>
        )}
        {/* --------------------------- */}

        <label>…o sube un archivo (mp4, mov, mkv)</label>
        <input type="file" accept="video/*" disabled />
        
        <div className="row">
          <div><label>Desde (opcional)</label><input name="from" placeholder="1:30:00" /></div>
          <div><label>Hasta (opcional)</label><input name="to" placeholder="2:30:00" /></div>
          <div><label>Duración de cada clip</label>
            <select name="secs" defaultValue="45"><option value="30">30 s</option><option value="45">45 s</option><option value="60">60 s</option><option value="90">90 s</option></select></div>
        </div>
        
        <div className="row">
          <div><label>Cuántos clips</label>
            <select name="count" defaultValue="15"><option>5</option><option>10</option><option>15</option><option>25</option></select></div>
          <div><label>Calidad</label>
            <select name="quality" defaultValue="2160p"><option value="720p">720p</option><option value="1080p">1080p</option><option value="1440p">1440p</option><option value="2160p">Máxima (4K, más nítido)</option></select></div>
          
          <div>
            <label>Formato del video</label>
            <select name="layout" defaultValue="crop">
              <option value="crop">Zoom a la cara</option>
              <option value="split">Pantalla dividida</option>
              <option value="blur">Fondo borroso</option>
            </select>
          </div>
        </div>

        <p className="sub" style={{ marginTop: 14, marginBottom: 0 }}>Para directos largos de Kick o Twitch, baja solo el tramo que te interesa.</p>
        <div style={{ marginTop: 16 }}><button className="btn" disabled={busy}>{busy ? "Enviando…" : "Analizar video"}</button></div>
        {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 16, marginBottom: 0 }}>{msg.text}</div>}
      </form>
    </>
  );
}
