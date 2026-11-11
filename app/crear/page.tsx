"use client";
import { useState } from "react";
import CropPreview from "@/components/CropPreview";

export default function Crear() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  
  const [videoUrl, setVideoUrl] = useState("");
  const [crop, setCrop] = useState({ x: 10, y: 10, w: 80, h: 60 });

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
        custom_crop: crop,
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
    <div style={{ display: "flex", gap: 20, alignItems: "flex-start", marginTop: 20 }}>
      
      {/* COLUMNA IZQUIERDA: FORMULARIO */}
      <div style={{ flex: 1, minWidth: 300 }}>
        <div className="card">
          <h3 style={{ marginBottom: 16, fontSize: 16, textTransform: "uppercase", color: "var(--muted)" }}>Source Video</h3>
          
          <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
            <button type="button" className="btn ghost sm" style={{ flex: 1, borderColor: "#53fc18", color: "#53fc18" }}>KICK</button>
            <button type="button" className="btn sm" style={{ flex: 1, background: "#9146ff" }}>TWITCH</button>
            <button type="button" className="btn ghost sm" style={{ flex: 1 }}>ARCHIVO</button>
          </div>

          <form onSubmit={submit}>
            <label>Pega el link del stream</label>
            <input 
              name="url" 
              placeholder="https://www.youtube.com/watch?v=..." 
              onChange={(e) => setVideoUrl(e.target.value)} 
              style={{ marginBottom: 10 }}
            />
            
            <button className="btn" style={{ width: "100%", marginBottom: 20 }} disabled={busy}>
              {busy ? "Importando..." : "Importar link"}
            </button>

            <div className="row">
              <div><label>Desde</label><input name="from" placeholder="0:00" /></div>
              <div><label>Hasta</label><input name="to" placeholder="1:00" /></div>
            </div>
            
            <div className="row">
              <div><label>Duración</label>
                <select name="secs" defaultValue="45"><option value="30">30 s</option><option value="45">45 s</option><option value="60">60 s</option></select></div>
              <div><label>Cantidad</label>
                <select name="count" defaultValue="5"><option>1</option><option>5</option><option>10</option></select></div>
            </div>

            <div className="row">
              <div><label>Calidad</label>
                <select name="quality" defaultValue="1080p"><option value="720p">720p</option><option value="1080p">1080p</option></select></div>
              <div><label>Formato</label>
                <select name="layout" defaultValue="crop">
                  <option value="crop">Vertical</option>
                  <option value="split">Dividido</option>
                  <option value="3x7">División 3x7</option>
                  <option value="blur">Fondo difuminado</option>
                </select>
              </div>
            </div>

            <div style={{ marginTop: 20 }}>
               <button className="btn" style={{ width: "100%" }} disabled={busy}>
                 {busy ? "Generando..." : "Generar clips"}
               </button>
            </div>
            {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 16 }}>{msg.text}</div>}
          </form>
        </div>
      </div>

      {/* COLUMNA CENTRAL: VISTA PREVIA TIPO TELÉFONO */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div className="card" style={{ width: "100%", maxWidth: 350, padding: 20, background: "transparent", border: "none" }}>
          <h3 style={{ textAlign: "center", marginBottom: 16, fontSize: 14, color: "var(--muted)" }}>ASÍ SE VEN TUS CLIPS</h3>
          
          {/* Mockup de Teléfono */}
          <div style={{ 
            width: "100%", aspectRatio: "9/16", background: "#000", borderRadius: 30, 
            border: "8px solid #222", overflow: "hidden", position: "relative",
            boxShadow: "0 0 20px rgba(46,230,214,0.2)"
          }}>
            {/* Si hay video, mostramos el CropPreview. Si no, un placeholder */}
            {videoUrl ? (
               <CropPreview videoUrl={videoUrl} onCropChange={(newCrop) => setCrop(newCrop)} />
            ) : (
              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#444", flexDirection: "column" }}>
                <span style={{ fontSize: 40 }}>▶</span>
                <span style={{ fontSize: 12, marginTop: 10 }}>Sube un video para previsualizar</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* COLUMNA DERECHA: INSTRUCCIONES */}
      <div style={{ flex: 1, minWidth: 280 }}>
        <div className="card">
          <h3 style={{ marginBottom: 16, fontSize: 16, textTransform: "uppercase", color: "var(--muted)" }}>Cómo funciona</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 14, lineHeight: "1.8" }}>
            <li style={{ display: "flex", gap: 10, marginBottom: 12 }}>
              <span style={{ background: "var(--cyan)", color: "#000", borderRadius: "50%", width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", flexShrink: 0 }}>1</span>
              <div><b>Subir el video</b><br/><span style={{ color: "var(--muted)" }}>Pega un link de YouTube o Twitch.</span></div>
            </li>
            <li style={{ display: "flex", gap: 10, marginBottom: 12 }}>
              <span style={{ background: "var(--cyan)", color: "#000", borderRadius: "50%", width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", flexShrink: 0 }}>2</span>
              <div><b>Elegir el encuadre</b><br/><span style={{ color: "var(--muted)" }}>Arrastra el recuadro en la vista previa.</span></div>
            </li>
            <li style={{ display: "flex", gap: 10, marginBottom: 12 }}>
              <span style={{ background: "var(--cyan)", color: "#000", borderRadius: "50%", width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", flexShrink: 0 }}>3</span>
              <div><b>Generar el clip</b><br/><span style={{ color: "var(--muted)" }}>La IA busca los mejores momentos.</span></div>
            </li>
            <li style={{ display: "flex", gap: 10 }}>
              <span style={{ background: "var(--cyan)", color: "#000", borderRadius: "50%", width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", flexShrink: 0 }}>4</span>
              <div><b>Descargar y publicar</b><br/><span style={{ color: "var(--muted)" }}>Listo para TikTok y Reels.</span></div>
            </li>
          </ul>
        </div>
      </div>

    </div>
  );
}
