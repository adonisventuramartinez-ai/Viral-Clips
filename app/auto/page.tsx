"use client";
import { useCallback, useEffect, useState } from "react";

type Feed = { id: string; name: string | null; kind: string; target: string; active: boolean; content_type: string; clips: number; max_age_hours: number; min_views: number; last_checked: string | null; last_status: string | null };
type Found = { id: string; title: string; url: string; views: number; status: string; reason: string | null; created_at: string };

const TYPES: [string, string][] = [["auto", "General"], ["reality", "Reality (Casa de Alofoke)"], ["podcast", "Podcast"], ["entrevista", "Entrevista"], ["juego", "Juegos"], ["gta6", "GTA 6"], ["gta_rp", "GTA RP"], ["directo", "Directo"]];

function ago(iso: string | null) {
  if (!iso) return "sin revisar";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 90 ? "hace un momento" : s < 3600 ? `hace ${Math.round(s / 60)} min` : `hace ${Math.round(s / 3600)} h`;
}

export default function Auto() {
  const [items, setItems] = useState<Feed[]>([]);
  const [found, setFound] = useState<Found[]>([]);
  const [on, setOn] = useState<boolean | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState("channel");

  const load = useCallback(async () => {
    const r = await fetch("/api/feeds", { cache: "no-store" }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) return setErr(j?.error ?? "No se pudo conectar");
    setErr(""); setItems(j.items ?? []); setFound(j.found ?? []); setOn(j.discover ?? null);
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);

  async function call(method: string, body: Record<string, unknown>) {
    const r = await fetch("/api/feeds", { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) setErr(j?.error ?? "No se pudo"); else setErr("");
    await load();
    return !!r?.ok;
  }
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget; const f = new FormData(form);
    setBusy(true);
    const ok = await call("POST", { kind, name: f.get("name"), target: f.get("target"), content_type: f.get("content_type"), clips: f.get("clips"), max_age_hours: f.get("max_age_hours"), min_views: f.get("min_views") });
    setBusy(false);
    if (ok) form.reset();
  }

  return (
    <>
      <h1>⚡ Clips automáticos</h1>
      <p className="sub">Vigila canales de YouTube, búsquedas o páginas de Facebook y saca clips solo de los videos nuevos que van más fuertes (más vistas por hora). Cada clip pasa por el área viral antes de publicarse.</p>
      {err && <div className="banner">{err}</div>}
      {!err && on !== null && (
        <div className={`banner ${on ? "ok" : ""}`}>{on ? "Clips automáticos ENCENDIDOS" : "Apagados: pon DISCOVER=1 en worker/.env y reinicia el worker."}</div>
      )}
      <form onSubmit={add} className="card" style={{ display: "grid", gap: 8 }}>
        <b>Agregar fuente</b>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="channel">Canal de YouTube</option>
            <option value="search">Búsqueda (lo más nuevo)</option>
            <option value="facebook">Página de Facebook</option>
          </select>
          <input name="name" placeholder="Nombre (opcional)" maxLength={60} />
        </div>
        <input name="target" required placeholder={kind === "channel" ? "https://www.youtube.com/@canal" : kind === "facebook" ? "https://www.facebook.com/NombreDePagina" : "La Casa de Alofoke 3"} />
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 8 }}>
          <select name="content_type">{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <input name="clips" type="number" min={1} max={15} defaultValue={4} title="Clips por video" />
          <input name="max_age_hours" type="number" min={1} defaultValue={48} title="Solo videos de las últimas N horas" />
          <input name="min_views" type="number" min={0} defaultValue={0} title="Vistas mínimas" />
        </div>
        {kind === "facebook" && <small style={{ color: "var(--muted)" }}>Facebook se lee con la Graph API y el FB_PAGE_TOKEN del worker: funciona con tus páginas, y con páginas de otros solo si tu app de Meta tiene el permiso «Page Public Content Access».</small>}
        <small style={{ color: "var(--muted)" }}>Clips por video · horas de antigüedad máxima · vistas mínimas. Respeta los derechos del contenido: usa solo canales de los que tengas permiso.</small>
        <button className="btn" disabled={busy}>{busy ? "Agregando…" : "Agregar"}</button>
      </form>
      <h3 style={{ marginTop: 20 }}>Mis fuentes ({items.length})</h3>
      <div style={{ display: "grid", gap: 8 }}>
        {items.map((f) => (
          <div key={f.id} className="card" style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ minWidth: 220 }}>
              <b>{f.name || f.target}</b> <small style={{ color: "var(--muted)" }}>{f.kind === "search" ? "búsqueda" : f.kind === "facebook" ? "Facebook" : "canal"} · {f.clips} clips/video · últimas {f.max_age_hours} h</small>
              <div><small style={{ color: "var(--muted)" }}>Revisada {ago(f.last_checked)} · {f.last_status ?? "—"}</small></div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn sm ghost" onClick={() => call("PATCH", { id: f.id, check_now: true })}>🔄 Revisar ya</button>
              <button className="btn sm ghost" onClick={() => call("PATCH", { id: f.id, active: !f.active })}>{f.active ? "⏸ Pausar" : "▶ Reanudar"}</button>
              <button className="btn sm ghost" onClick={() => confirm("¿Quitar esta fuente?") && call("DELETE", { id: f.id })}>🗑</button>
            </div>
          </div>
        ))}
        {!items.length && <small style={{ color: "var(--muted)" }}>Aún no hay fuentes.</small>}
      </div>
      <h3 style={{ marginTop: 20 }}>Lo que encontró</h3>
      <div style={{ display: "grid", gap: 6 }}>
        {found.map((v) => (
          <div key={v.id} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 13 }}>
            <span>{v.status === "queued" ? "⚡" : "⏭"} <a href={v.url} target="_blank" rel="noreferrer">{v.title}</a> <small style={{ color: "var(--muted)" }}>{v.views.toLocaleString()} vistas{v.reason ? ` · ${v.reason}` : ""}</small></span>
            <small style={{ color: "var(--muted)" }}>{ago(v.created_at)}</small>
          </div>
        ))}
        {!found.length && <small style={{ color: "var(--muted)" }}>Nada todavía.</small>}
      </div>
    </>
  );
}
