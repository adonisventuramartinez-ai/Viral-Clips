"use client";
import { useCallback, useEffect, useState } from "react";

type Ch = {
  id: string; name: string | null; url: string; active: boolean; content_type: string; game: string | null;
  layout: string; clip_seconds: number; last_checked: string | null; last_status: string | null;
};

const TYPE_LABEL: Record<string, string> = { auto: "General", podcast: "Podcast", entrevista: "Entrevista", juego: "Juegos", directo: "Directo (charla)" };

function ago(iso: string | null) {
  if (!iso) return "sin revisar";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 90 ? "hace un momento" : s < 3600 ? `hace ${Math.round(s / 60)} min` : `hace ${Math.round(s / 3600)} h`;
}

// Canales que el worker vigila: cuando entran en vivo, empieza a grabar solo.
export default function WatchChannels() {
  const [items, setItems] = useState<Ch[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [ctype, setCtype] = useState("auto");

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/watch", { cache: "no-store" });
      const j = await r.json();
      setItems(j.items ?? []);
      setErr(r.ok ? "" : j.error ?? "Error al cargar");
    } catch {
      setErr("No se pudo conectar con el servidor");
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    const res = await fetch("/api/watch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: f.get("name"), url: f.get("url"), content_type: ctype, game: ctype === "juego" ? f.get("game") : "",
        layout: f.get("layout"), clip_seconds: Number(f.get("secs")),
        clipper: (() => { try { return localStorage.getItem("cf_clipper") || null; } catch { return null; } })(),
      }),
    });
    const j = await res.json();
    if (!res.ok) setErr(j.error ?? "No se pudo agregar");
    else form.reset();
    await load();
    setBusy(false);
  }

  async function toggle(c: Ch) {
    await fetch("/api/watch", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: c.id, active: !c.active }) });
    load();
  }
  async function remove(c: Ch) {
    if (!confirm(`¿Quitar "${c.name || c.url}"?`)) return;
    await fetch("/api/watch", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: c.id }) });
    load();
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h4 style={{ fontSize: 14, color: "var(--muted)" }}>Canales automáticos · {items.length}</h4>
      <p className="sub" style={{ margin: "6px 0 12px" }}>
        El worker mira estos canales cada pocos minutos y, cuando uno entra en vivo, empieza a grabar y a sacar clips solo
        (si no está ocupado con otro directo). Necesita el worker encendido.
      </p>
      {err && <div className="banner">{err}</div>}

      {items.map((c) => (
        <div key={c.id} style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between", padding: "8px 0", borderTop: "1px solid var(--line)", flexWrap: "wrap" }}>
          <div style={{ minWidth: 0 }}>
            <b>{c.name || c.url}</b>{" "}
            <span style={{ color: "var(--muted)", fontSize: 12 }}>
              · {TYPE_LABEL[c.content_type] ?? c.content_type}{c.game ? ` (${c.game})` : ""} · {c.clip_seconds}s
            </span>
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              {c.active ? `${c.last_status ?? "esperando"} · revisado ${ago(c.last_checked)}` : "pausado"}
            </div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn sm ghost" onClick={() => toggle(c)}>{c.active ? "Pausar" : "Activar"}</button>
            <button className="btn sm ghost" onClick={() => remove(c)}>Quitar</button>
          </div>
        </div>
      ))}

      <form onSubmit={add} style={{ marginTop: 12 }}>
        <div className="row" style={{ gridTemplateColumns: "1fr 2fr" }}>
          <div><label>Nombre (opcional)</label><input name="name" placeholder="ej. Mi streamer" maxLength={60} /></div>
          <div><label>Link del canal</label><input name="url" placeholder="https://www.youtube.com/@canal  ·  https://www.twitch.tv/canal" required /></div>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <div><label>Tipo de contenido</label>
            <select value={ctype} onChange={(e) => setCtype(e.target.value)}>
              {Object.entries(TYPE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select></div>
          <div><label>Duración de cada clip</label>
            <select name="secs" defaultValue="45"><option value="30">30 s</option><option value="45">45 s</option><option value="60">60 s</option><option value="90">90 s</option></select></div>
          <div><label>Formato</label>
            <select name="layout" defaultValue="crop"><option value="crop">Zoom a la cara</option><option value="split">Dividido: cara grande</option><option value="split_eq">Dividido: equilibrado</option><option value="split_game">Dividido: juego grande</option><option value="duo">Dos personas</option><option value="blur">Fondo borroso</option></select></div>
        </div>
        {ctype === "juego" && <input name="game" placeholder="¿Qué juego? (ej. Valorant, Fortnite)" maxLength={60} style={{ marginTop: 10 }} />}
        <div style={{ marginTop: 12 }}><button className="btn sm" disabled={busy}>{busy ? "Agregando…" : "+ Agregar canal"}</button></div>
      </form>
    </div>
  );
}
