"use client";
import { useState } from "react";
import { postHub } from "@/lib/useHub";

export default function Promo() {
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  async function send(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = e.currentTarget;
    const b = Object.fromEntries(new FormData(f));
    const err = await postHub("promos", b);
    setMsg(err ? { ok: false, t: err } : { ok: true, t: "¡Recibido! Te contactamos pronto." });
    if (!err) f.reset();
  }
  return (
    <>
      <h1>📣 Publicitá tu canal</h1>
      <p className="sub">Mostrá tu canal, marca o servicio a toda la comunidad en los banners de arriba.</p>
      <form className="card" onSubmit={send} style={{ maxWidth: 560 }}>
        <label style={{ marginTop: 0 }}>Nombre del canal o marca</label><input name="name" required maxLength={80} />
        <label>Link del canal</label><input name="channel_url" placeholder="https://twitch.tv/…" />
        <label>Tu contacto (Discord / WhatsApp / email)</label><input name="contact" required maxLength={120} />
        <label>Mensaje del banner</label><textarea name="message" rows={3} maxLength={400} />
        <button className="btn" style={{ marginTop: 16 }}>Enviar solicitud</button>
        {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 14, marginBottom: 0 }}>{msg.t}</div>}
      </form>
      <small style={{ display: "block", marginTop: 12, color: "var(--muted)" }}>Apruebas cada promo poniendo <code>active = true</code> en la tabla <code>promo_requests</code> de Supabase.</small>
    </>
  );
}
