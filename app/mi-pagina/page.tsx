"use client";
import { useCallback, useEffect, useState } from "react";

type Pack = { posts: number; views: number; likes: number; comments: number; shares: number; avg: number };
type Hour = { network: string; slot: string; score: number; posts: number; chosen: boolean; explore: boolean };
type Data = {
  days: number; totals: Pack | null; byNet: Record<string, Pack>;
  top: { title: string; network: string; views: number; likes: number; comments: number; shares: number; publishedAt: string | null }[];
  hours: Record<string, Hour[]>; followers: Record<string, { now: number; delta7: number | null; delta30: number | null }>;
  upcoming: { network: string; scheduled_at: string; clips: { title: string } | { title: string }[] | null }[];
  errors: number; lastFetch: string | null; defaults: string[];
  learning: { have: number; need: number; on: boolean | null; stats: boolean | null };
};

const NET: Record<string, string> = { facebook: "Facebook", instagram: "Instagram", youtube: "YouTube Shorts", all: "Todas las redes" };
const n = (v: number) => (v >= 1_000_000 ? (v / 1_000_000).toFixed(1) + " M" : v >= 10_000 ? Math.round(v / 1000) + " mil" : v.toLocaleString());
const sign = (v: number | null) => (v === null ? "—" : (v > 0 ? "+" : "") + v.toLocaleString());
function ago(iso: string | null) {
  if (!iso) return "nunca";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 90 ? "hace un momento" : s < 3600 ? `hace ${Math.round(s / 60)} min` : s < 86400 ? `hace ${Math.round(s / 3600)} h` : `hace ${Math.round(s / 86400)} d`;
}
const label12 = (slot: string) => { const [h, m] = slot.split(":").map(Number); return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "a. m." : "p. m."}`; };

export default function MiPagina() {
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  const [days, setDays] = useState(30);
  const [net, setNet] = useState("all");

  const load = useCallback(async () => {
    const r = await fetch(`/api/pagina?days=${days}`, { cache: "no-store" }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) return setErr(j?.error ?? "No se pudo conectar");
    setErr(""); setD(j);
  }, [days]);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);

  const k = (label: string, v: string | number, sub?: string) => (
    <div className="card"><small style={{ color: "var(--muted)" }}>{label}</small><div style={{ fontSize: 30, fontWeight: 700 }}>{v}</div>{sub && <small style={{ color: "var(--muted)" }}>{sub}</small>}</div>
  );
  const t = d?.totals;
  const hrs = (d?.hours[net] ?? d?.hours.all ?? []);
  const usingAll = net !== "all" && !d?.hours[net] && !!d?.hours.all;
  const maxScore = Math.max(1.2, ...hrs.map((h) => h.score));
  const chosen = hrs.filter((h) => h.chosen).map((h) => h.slot);
  const prog = d ? Math.min(100, Math.round((d.learning.have / Math.max(1, d.learning.need)) * 100)) : 0;
  const nets = Object.keys(d?.byNet ?? {});

  return (
    <>
      <h1>📈 Mi página</h1>
      <p className="sub">Cómo le va a lo que publicas en Facebook, Instagram y YouTube Shorts, y a qué horas rinde mejor. El worker lee los números solo.</p>
      {err && <div className="banner">{err}</div>}
      {d && d.learning.stats === false && <div className="banner">Las estadísticas están apagadas (STATS=0 en worker/.env).</div>}
      {d && !err && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
          {[7, 30, 90].map((x) => <button key={x} className={`btn sm ${days === x ? "" : "ghost"}`} onClick={() => setDays(x)}>Últimos {x} días</button>)}
          <small style={{ color: "var(--muted)" }}>Números leídos {ago(d.lastFetch)}{d.errors ? ` · ${d.errors} publicación(es) sin poder leerse` : ""}</small>
        </div>
      )}

      {d && t && t.posts === 0 && !err && (
        <div className="card">Aún no hay publicaciones con números. Cuando el worker publique (o leas lo que ya publicaste desde la Cola), aquí aparecen las vistas, likes y comentarios, normalmente en la hora siguiente.</div>
      )}

      {d && t && t.posts > 0 && (
        <>
          <div className="grid3" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            {k("Publicaciones", t.posts)}{k("Vistas", n(t.views), `${n(t.avg)} por publicación`)}{k("Likes", n(t.likes))}{k("Comentarios", n(t.comments), t.shares ? `${n(t.shares)} compartidos` : undefined)}
          </div>

          <h3 style={{ marginTop: 22 }}>Por red</h3>
          <div style={{ display: "grid", gap: 8 }}>
            {nets.map((x) => {
              const p = d.byNet[x]; const f = d.followers[x];
              return (
                <div key={x} className="card" style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <div style={{ minWidth: 180 }}><b>{NET[x]}</b><div><small style={{ color: "var(--muted)" }}>{p.posts} publicaciones</small></div></div>
                  <div style={{ display: "flex", gap: 22, flexWrap: "wrap" }}>
                    <div><small style={{ color: "var(--muted)" }}>Vistas</small><div><b>{n(p.views)}</b></div></div>
                    <div><small style={{ color: "var(--muted)" }}>Promedio</small><div><b>{n(p.avg)}</b></div></div>
                    <div><small style={{ color: "var(--muted)" }}>Likes</small><div><b>{n(p.likes)}</b></div></div>
                    <div><small style={{ color: "var(--muted)" }}>Comentarios</small><div><b>{n(p.comments)}</b></div></div>
                    {f && <div><small style={{ color: "var(--muted)" }}>Seguidores</small><div><b>{n(f.now)}</b> <small style={{ color: "var(--muted)" }}>{sign(f.delta7)} en 7 d</small></div></div>}
                  </div>
                </div>
              );
            })}
          </div>

          <h3 style={{ marginTop: 22 }}>Lo que mejor te ha funcionado</h3>
          <div style={{ display: "grid", gap: 6 }}>
            {d.top.map((c, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 14 }}>
                <span>{i + 1}. {c.title} <small style={{ color: "var(--muted)" }}>· {NET[c.network] ?? c.network}</small></span>
                <span><b>{n(c.views)}</b> <small style={{ color: "var(--muted)" }}>vistas · {n(c.likes)} ♥ · {n(c.comments)} 💬</small></span>
              </div>
            ))}
          </div>
        </>
      )}

      {d && !err && (
        <>
          <h3 style={{ marginTop: 22 }}>🕐 Tus mejores horas</h3>
          <div className="card">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
              {["all", "facebook", "instagram", "youtube"].map((x) => <button key={x} className={`btn sm ${net === x ? "" : "ghost"}`} onClick={() => setNet(x)}>{NET[x]}</button>)}
            </div>
            {hrs.length ? (
              <>
                <div style={{ marginBottom: 10 }}>
                  Se publica a las <b>{chosen.map(label12).join(" · ") || "—"}</b>{usingAll && <small style={{ color: "var(--muted)" }}> (esta red aún no tiene suficientes datos propios: usa los de todas)</small>}
                </div>
                <div style={{ display: "grid", gap: 6 }}>
                  {hrs.map((h) => (
                    <div key={h.slot} style={{ display: "grid", gridTemplateColumns: "84px 1fr 150px", gap: 10, alignItems: "center", fontSize: 13 }}>
                      <span style={{ fontWeight: h.chosen ? 700 : 400 }}>{label12(h.slot)}</span>
                      <div style={{ background: "var(--line)", borderRadius: 6, height: 12 }}><div style={{ width: `${Math.max(2, (h.score / maxScore) * 100)}%`, height: 12, borderRadius: 6, background: h.chosen ? "var(--grad)" : "var(--muted)", opacity: h.chosen ? 1 : 0.45 }} /></div>
                      <small style={{ color: "var(--muted)" }}>{h.score ? `${h.score.toFixed(2)}× tu promedio` : "sin datos"} · {h.posts} pub.{h.explore ? " · 🧪 de prueba" : ""}</small>
                    </div>
                  ))}
                </div>
                <small style={{ color: "var(--muted)", display: "block", marginTop: 10 }}>1.00× es el promedio de esa red. Una hora marcada 🧪 se prueba a propósito para seguir descubriendo; si rinde, pasa a ser una de las mejores.</small>
              </>
            ) : (
              <>
                <div>Todavía se usan las horas de siempre: <b>{d.defaults.map(label12).join(" · ")}</b>.</div>
                <div style={{ background: "var(--line)", borderRadius: 6, height: 12, margin: "10px 0 4px" }}><div style={{ width: `${prog}%`, height: 12, borderRadius: 6, background: "var(--grad)" }} /></div>
                <small style={{ color: "var(--muted)" }}>
                  {d.learning.have} de {d.learning.need} publicaciones con más de 24 h para aprender de tus datos
                  {d.learning.on === false ? " · el aprendizaje está apagado (LEARN_SLOTS=0)" : "."}
                </small>
              </>
            )}
          </div>

          {d.upcoming.length > 0 && (
            <>
              <h3 style={{ marginTop: 22 }}>Lo próximo en la cola</h3>
              <div style={{ display: "grid", gap: 6 }}>
                {d.upcoming.map((p, i) => {
                  const c = Array.isArray(p.clips) ? p.clips[0] : p.clips;
                  return <div key={i} style={{ fontSize: 14 }}>⏳ {c?.title ?? "(clip)"} <small style={{ color: "var(--muted)" }}>· {NET[p.network] ?? p.network} · {new Date(p.scheduled_at).toLocaleString()}</small></div>;
                })}
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
