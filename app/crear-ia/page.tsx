"use client";
import { useState } from "react";

const STYLES: [string, string][] = [
  ["realista", "Realista · cinematográfico"],
  ["anime", "Anime · ilustrado"],
  ["cyberpunk", "Cyberpunk · neón"],
  ["cartoon", "Cartoon · colorido"],
  ["3d", "3D ·render animado"],
];

export default function CrearIA() {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("realista");
  const [music, setMusic] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const text = prompt.trim();
    if (text.length < 5) { setMsg({ ok: false, text: "Escribe una descripción de al menos 5 caracteres." }); return; }
    setBusy(true); setMsg(null);
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "text_to_video", prompt: text, style, music }),
      });
      const data = await res.json().catch(() => ({}));
      if (data.demo) { setMsg({ ok: true, text: data.message }); setBusy(false); return; }
      if (!res.ok) { setMsg({ ok: false, text: data.error ?? "No se pudo encolar el video." }); setBusy(false); return; }
      window.location.href = "/biblioteca";
    } catch {
      setMsg({ ok: false, text: "No se pudo conectar con el servidor." });
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Crear con IA</h1>
      <p className="sub">
        Escribe una escena y el worker genera un video vertical de <b>60 segundos exactos</b> (9:16),
        con subtítulos, logo y música opcional. Listo para Facebook, Reels o Shorts.
      </p>

      <form className="card" onSubmit={submit} style={{ maxWidth: 720 }}>
        <label htmlFor="prompt">Descripción de la escena</label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ej. Un gato montando en monopatín por una calle de Miami al atardecer, con palmeras y luces de neón"
          rows={5}
          maxLength={600}
          required
        />
        <small style={{ display: "block", color: "var(--muted)", marginTop: 6 }}>
          {prompt.length}/600 · Sé concreto: quién, dónde y qué hace.
        </small>

        <div className="row" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 18 }}>
          <div>
            <label htmlFor="style">Estilo visual</label>
            <select id="style" value={style} onChange={(e) => setStyle(e.target.value)}>
              {STYLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="music">Audio</label>
            <label htmlFor="music" style={{ display: "flex", gap: 8, alignItems: "center", textTransform: "none", fontWeight: 500 }}>
              <input id="music" type="checkbox" checked={music} onChange={(e) => setMusic(e.target.checked)} style={{ width: "auto" }} />
              Música de fondo (libre de regalías)
            </label>
          </div>
        </div>

        <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 14, margin: "18px 0", lineHeight: 1.6, fontSize: 13, color: "var(--muted)" }}>
          <b style={{ color: "var(--text)" }}>Cómo funciona (free tier):</b> se generan 4 escenas cortas con la
          API de Hugging Face y se extienden a 15 s cada una con ffmpeg hasta completar 60 s. La primera vez
          el modelo puede tardar en “despertar” (cold start); el worker reintenta automáticamente.
          Necesitas <code>HF_TOKEN</code> en <code>worker/.env</code>.
        </div>

        <button className="btn" disabled={busy}>
          {busy ? "Generando… (puede tardar varios minutos)" : "✨ Crear video de 60 s"}
        </button>
        {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 14, marginBottom: 0 }}>{msg.text}</div>}
      </form>
    </>
  );
}
