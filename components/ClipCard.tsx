"use client";
import { useState } from "react";
import type { Clip } from "@/lib/types";

const TAGS = ["#fyp", "#viral", "#clips", "#streamer"];
type Net = "tiktok" | "shorts" | "reels";
const uniq = (a: string[]) => a.filter((t, i) => a.findIndex((x) => x.toLowerCase() === t.toLowerCase()) === i);

export default function ClipCard({ clip, onDeleted, onAdjusted }: { clip: Clip; onDeleted?: (id: string) => void; onAdjusted?: () => void }) {
  const real = Boolean(clip.videoUrl);
  const [busy, setBusy] = useState(false);
  const [pub, setPub] = useState(clip.isPublic ?? true);
  const [copied, setCopied] = useState<Net | "">("");
  const [adj, setAdj] = useState(false);
  const [a, setA] = useState({ start: clip.start, end: clip.end, layout: "" });
  const [hooks, setHooks] = useState(false);
  const [when, setWhen] = useState("");
  const [sched, setSched] = useState<{ at?: string; status?: string; error?: string }>({ at: clip.scheduledAt, status: clip.publishStatus, error: clip.publishError });
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  async function adjust() {
    setBusy(true); setNote(null);
    const r = await fetch(`/api/clips/${clip.id}/rerender`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ start: a.start, end: a.end, layout: a.layout || undefined }),
    }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy(false);
    if (r?.ok) { setNote({ ok: true, text: "En cola: el worker lo rehace y se actualiza solo." }); setAdj(false); onAdjusted?.(); }
    else setNote({ ok: false, text: j?.error ?? "No se pudo pedir el ajuste" });
  }

  // Gancho alternativo: rehace el clip con otro texto arriba (para probar A/B publicando las dos versiones)
  async function tryHook(h: string) {
    setBusy(true); setNote(null);
    const r = await fetch(`/api/clips/${clip.id}/rerender`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ start: a.start, end: a.end, hook: h }),
    }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy(false);
    if (r?.ok) { setNote({ ok: true, text: "En cola: el worker rehace el clip con ese gancho." }); onAdjusted?.(); }
    else setNote({ ok: false, text: j?.error ?? "No se pudo pedir el cambio" });
  }

  async function schedule(cancel = false) {
    if (!cancel && !when) return setNote({ ok: false, text: "Elige fecha y hora" });
    setBusy(true); setNote(null);
    const r = await fetch(`/api/clips/${clip.id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_at: cancel ? null : new Date(when).toISOString() }),
    }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy(false);
    if (r?.ok) {
      setSched(cancel ? {} : { at: new Date(when).toISOString(), status: "scheduled" });
      setNote({ ok: true, text: cancel ? "Programación cancelada." : "Programado. El worker lo publica en tu página de Facebook a esa hora (necesita FB_PAGE_ID y FB_PAGE_TOKEN)." });
    } else setNote({ ok: false, text: j?.error ?? "No se pudo programar" });
  }

  async function remove() {
    if (!confirm("¿Seguro que quieres eliminar este clip para siempre?")) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/clips/${clip.id}`, { method: "DELETE" });
      if (res.ok) return onDeleted ? onDeleted(clip.id) : window.location.reload();
      const j = await res.json().catch(() => ({}));
      alert(j.error || "Error al eliminar el clip");
    } catch {
      alert("Error de conexión");
    }
    setBusy(false);
  }

  async function togglePublic() {
    const next = !pub;
    setPub(next);
    const res = await fetch(`/api/clips/${clip.id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_public: next }),
    }).catch(() => null);
    if (!res || !res.ok) setPub(!next);
  }

  // Texto listo para pegar en cada red. Con paquete (clips nuevos) usa el texto propio de cada red; si no, la descripción y hashtags de siempre.
  function textFor(net: Net) {
    const p = clip.pack;
    if (net === "tiktok" && p?.tiktok?.caption) return `${p.tiktok.caption}\n${(p.tiktok.hashtags ?? []).join(" ")}`;
    if (net === "reels" && p?.reels?.caption) return `${p.reels.caption}\n${(p.reels.hashtags ?? []).join(" ")}`;
    if (net === "shorts" && p?.shorts?.title) return `${p.shorts.title}\n${p.shorts.description ? p.shorts.description + "\n" : ""}${(p.shorts.hashtags ?? []).join(" ")}`;
    const tags = clip.hashtags && clip.hashtags.length ? clip.hashtags : TAGS;
    const desc = clip.description ?? "";
    if (net === "tiktok") return `${clip.title}\n${uniq([...tags.slice(0, 5), "#fyp"]).join(" ")}`;
    if (net === "shorts") return `${clip.title}\n${desc ? desc + "\n" : ""}${uniq([...tags.slice(0, 4), "#Shorts"]).join(" ")}`;
    return `${desc || clip.title}\n${tags.slice(0, 8).join(" ")}`;
  }

  async function copyText(net: Net) {
    try {
      await navigator.clipboard.writeText(textFor(net));
      setCopied(net);
      setTimeout(() => setCopied(""), 1800);
    } catch { /* sin permiso de portapapeles */ }
  }

  return (
    <div className="clip">
      <div className="v" style={real ? { background: "#000", padding: 0 } : { background: clip.thumb }}>
        {real ? (
          <video src={clip.videoUrl} poster={clip.thumbUrl} controls playsInline preload="metadata" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <>
            <span className="tag">{clip.start}–{clip.end}</span>
            <span className="play">▶</span>
            <div className="cap">{clip.captions}</div>
          </>
        )}
      </div>
      <div className="meta">
        <p>{clip.title}</p>
        <small><span className="viral">{clip.score}% viral</span> · {clip.seconds ? `${clip.seconds} s · ` : ""}{clip.sizeMb} MB · {clip.start}–{clip.end}</small>
        {clip.reason && <small style={{ display: "block", marginTop: 6, fontFamily: "inherit" }}>{clip.reason}</small>}

        <div className="acts">
          {clip.downloadUrl
            ? <a className="btn sm" href={clip.downloadUrl} style={{ textAlign: "center" }}>Descargar</a>
            : <button className="btn sm" disabled>Descargar</button>}
          {(["tiktok", "shorts", "reels"] as Net[]).map((n) => (
            <button key={n} className="btn sm ghost" onClick={() => copyText(n)} title="Copia título, descripción y hashtags para esa red">
              {copied === n ? "¡Copiado!" : `📋 ${n === "tiktok" ? "TikTok" : n === "shorts" ? "Shorts" : "Reels"}`}
            </button>
          ))}
          <button className="btn sm ghost" onClick={togglePublic} title="Si está público aparece en el Top y el feed de la comunidad">
            {pub ? "🌐 Público" : "🔒 Privado"}
          </button>
          {clip.pack?.hooks?.length ? <button className="btn sm ghost" onClick={() => setHooks(!hooks)} title="Otros 3 textos para el arranque del clip">🎣 Ganchos</button> : null}
          {clip.thumbUrl && <a className="btn sm ghost" href={clip.thumbUrl} target="_blank" rel="noreferrer" style={{ textAlign: "center" }} title="Miniatura automática">🖼 Miniatura</a>}
          <button className="btn sm ghost" onClick={() => setAdj(!adj)}>✏️ Ajustar</button>
          <button className="btn sm" onClick={remove} disabled={busy} style={{ background: "#ef4444", color: "#fff", border: "none" }}>
            {busy ? "Eliminando…" : "Eliminar clip"}
          </button>
        </div>
        {hooks && clip.pack?.hooks && (
          <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
            <small style={{ color: "var(--muted)" }}>Prueba otro gancho: el worker rehace el clip con ese texto arriba. Publica las dos versiones y compara.</small>
            {clip.pack.hooks.map((h) => (
              <div key={h} style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13 }}>{h}</span>
                <button className="btn sm ghost" onClick={() => tryHook(h)} disabled={busy}>Usar</button>
              </div>
            ))}
            {clip.pack.first_comment && <small style={{ color: "var(--muted)" }}>💬 Comentario para fijar: {clip.pack.first_comment}</small>}
          </div>
        )}
        <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
          {sched.status === "scheduled" && sched.at && <small>🗓 Programado: {new Date(sched.at).toLocaleString()} · <a href="#" onClick={(e) => { e.preventDefault(); schedule(true); }}>cancelar</a></small>}
          {sched.status === "published" && <small>✅ Publicado en Facebook</small>}
          {sched.status === "error" && <small style={{ color: "#ef4444" }}>⚠️ No se publicó: {sched.error}</small>}
          {sched.status !== "published" && sched.status !== "scheduled" && (
            <div style={{ display: "flex", gap: 8 }}>
              <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} style={{ flex: 1 }} aria-label="Programar publicación en Facebook" />
              <button className="btn sm ghost" onClick={() => schedule()} disabled={busy}>🗓 Programar</button>
            </div>
          )}
        </div>
        {adj && (
          <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
            <small style={{ color: "var(--muted)" }}>Tiempos del video original (ej. 12:30). Cambia el inicio/fin o el encuadre y el worker lo rehace.</small>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <input value={a.start} onChange={(e) => setA({ ...a, start: e.target.value })} placeholder="Inicio" />
              <input value={a.end} onChange={(e) => setA({ ...a, end: e.target.value })} placeholder="Fin" />
            </div>
            <select value={a.layout} onChange={(e) => setA({ ...a, layout: e.target.value })}>
              <option value="">Mismo encuadre</option>
              <option value="crop">Vertical</option>
              <option value="split">Dividido: cara grande</option>
              <option value="split_eq">Dividido: equilibrado</option>
              <option value="split_game">Dividido: juego grande</option>
              <option value="duo">Dos personas</option>
              <option value="blur">Fondo difuminado</option>
            </select>
            <button className="btn sm" onClick={adjust} disabled={busy}>{busy ? "Enviando…" : "Rehacer clip"}</button>
          </div>
        )}
        {note && <div className={`banner ${note.ok ? "ok" : ""}`} style={{ marginTop: 8, marginBottom: 0, fontSize: 12 }}>{note.text}</div>}
      </div>
    </div>
  );
}
