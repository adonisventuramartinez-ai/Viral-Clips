"use client";
import { useState } from "react";

export default function Resumen() {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    const r = await fetch("/api/summarize", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy(false);
    if (r?.ok) setMsg({ ok: true, text: "En cola: el worker genera el resumen narrado (1 clip de ~90 s). Míralo en Biblioteca." });
    else setMsg({ ok: false, text: j?.error ?? "No se pudo encolar" });
  }

  return (
    <>
      <h1>Crear resumen</h1>
      <p className="sub">Pega un video largo y el worker genera UN clip narrado de ~90 s con lo mejor, con voz contando el contexto (Modo Original).</p>
      <form className="card" onSubmit={submit} style={{ maxWidth: 640 }}>
        <label>Link del video (YouTube, etc.)</label>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=..." required />
        <div style={{ marginTop: 14 }}>
          <button className="btn" disabled={busy}>{busy ? "Encolando…" : "Crear resumen narrado"}</button>
        </div>
        {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 10 }}>{msg.text}</div>}
      </form>
    </>
  );
}