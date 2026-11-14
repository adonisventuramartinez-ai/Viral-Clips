"use client";
import { useCallback, useEffect, useState } from "react";
import Ring from "@/components/Ring";
import ClipCard from "@/components/ClipCard";
import WatchChannels from "@/components/WatchChannels";
import { ACTIVE, fmtTime } from "@/lib/format";
import type { Clip, LiveStep, Rejected } from "@/lib/types";

type Progress = { recorded_sec?: number; transcribed_sec?: number; reviews?: number; clips?: number; reconnects?: number; state?: string; chat_msgs?: number; pending_now?: number };
type Src = { id: string; title: string | null; url: string | null; status: string; error: string | null; progress: Progress | null };

function buildSteps(s: Src, clipCount: number): LiveStep[] {
  const p = s.progress ?? {};
  const live = ACTIVE.includes(s.status);
  const started = s.status !== "queued";
  const st = (on: boolean): "done" | "active" | "wait" => (!live ? "done" : on ? "active" : "wait");
  return [
    { label: "Conectando con el directo", detail: "", state: started ? "done" : "active" },
    { label: live ? "Grabando" : "Grabación terminada", detail: p.recorded_sec ? fmtTime(p.recorded_sec) : "", state: started ? st(true) : "wait" },
    { label: "Transcribiendo", detail: p.transcribed_sec ? fmtTime(p.transcribed_sec) : "", state: started ? st(true) : "wait" },
    { label: "Buscando momentos virales", detail: `${p.reviews ?? 0} revisiones`, state: started ? st(true) : "wait" },
    { label: "Creando clips", detail: `${clipCount} listos`, state: started ? st(true) : "wait" },
  ];
}

export default function EnVivo() {
  const [source, setSource] = useState<Src | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [rejected, setRejected] = useState<Rejected[]>([]);
  const [worker, setWorker] = useState<boolean | null>(null);
  const [demo, setDemo] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [ctype, setCtype] = useState("auto");
  const [nowMsg, setNowMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/live", { cache: "no-store" });
      const j = await r.json();
      if (!r.ok) {
        setErr(j.error ?? "Error al cargar");
        return;
      }
      setErr("");
      setDemo(!!j.demo);
      setWorker(j.worker ?? null);
      setSource(j.source);
      setRejected(j.rejected ?? []);
      // conserva las URLs ya cargadas para que el reproductor no se reinicie
      setClips((prev) =>
        (j.clips as Clip[]).map((c) => {
          const old = prev.find((p) => p.id === c.id);
          return old ? { ...c, videoUrl: old.videoUrl ?? c.videoUrl, downloadUrl: old.downloadUrl ?? c.downloadUrl } : c;
        }),
      );
    } catch {
      setErr("No se pudo conectar con el servidor");
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  async function start(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const f = new FormData(e.currentTarget);
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "live",
        url: f.get("url"),
        clip_seconds: Number(f.get("secs")),
        quality: f.get("quality"),
        review_minutes: Number(f.get("review")),
        layout: f.get("layout"),
        content_type: ctype,
        game: ctype === "juego" ? String(f.get("game") ?? "").trim() : "",
        max_new: Number(f.get("max_new")),
        progress_bar: f.get("bar") === "on",
        clipper: (() => { try { return localStorage.getItem("cf_clipper") || null; } catch { return null; } })(),
      }),
    });
    const j = await res.json();
    if (!res.ok) setErr(j.error ?? "No se pudo empezar");
    else if (j.demo) setErr(j.message);
    await load();
    setBusy(false);
  }

  async function stop() {
    if (!source) return;
    setBusy(true);
    await fetch("/api/live/stop", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_id: source.id }) });
    await load();
    setBusy(false);
  }

  async function clipNow() {
    if (!source) return;
    setBusy(true);
    setNowMsg("");
    const r = await fetch("/api/live/clip", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_id: source.id, seconds: 45 }) });
    const j = await r.json().catch(() => ({}));
    setNowMsg(r.ok ? "Pedido enviado: el clip sale en cuanto termine el trozo que se está grabando (menos de un minuto)." : j.error ?? "No se pudo pedir el clip");
    await load();
    setBusy(false);
  }

  const active = !!source && ACTIVE.includes(source.status);
  const p = source?.progress ?? {};

  return (
    <>
      <h1>En vivo</h1>
      <p className="sub">Graba un directo y va sacando clips mientras ocurre. Puedes dejar esta pantalla abierta.</p>

      {demo && <div className="banner">Supabase no está conectado.</div>}
      {err && <div className="banner">{err}</div>}
      {worker === false && (!source || active) && (
        <div className="banner">El worker está apagado. Enciéndelo en tu PC (docker run …) para que grabe y saque clips.</div>
      )}

      {!active && (
        <form className="card" style={{ marginBottom: 16 }} onSubmit={start}>
          <label>Link del directo (YouTube, Twitch o Kick)</label>
          <input name="url" placeholder="https://www.youtube.com/watch?v=..." required />
          
          <div className="row">
            <div><label>Duración de cada clip</label>
              <select name="secs" defaultValue="0"><option value="0">Automática (según el tipo)</option><option value="15">15 s</option><option value="20">20 s</option><option value="30">30 s</option><option value="45">45 s</option><option value="60">60 s</option><option value="75">75 s</option><option value="90">90 s</option></select></div>
            <div><label>Revisar cada</label>
              <select name="review" defaultValue="2"><option value="1">1 min</option><option value="2">2 min</option><option value="5">5 min</option></select></div>
            <div><label>Calidad</label>
              <select name="quality" defaultValue="720p"><option value="720p">720p</option><option value="1080p">1080p</option><option value="1440p">1440p (2K)</option><option value="2160p">2160p (4K)</option></select></div>
          </div>

          {/* --- NUEVO: Selector de Formato --- */}
          <div style={{ marginTop: 14 }}>
            <label>Formato del video</label>
            <select name="layout" defaultValue="crop">
              <option value="crop">Zoom a la cara</option>
              <option value="split">Dividido: cara grande</option>
              <option value="split_eq">Dividido: equilibrado</option>
              <option value="split_game">Dividido: juego grande</option>
              <option value="duo">Dos personas (una arriba, otra abajo)</option>
              <option value="blur">Fondo borroso</option>
            </select>
          </div>

          <div className="row" style={{ marginTop: 14, gridTemplateColumns: "1fr 1fr" }}>
            <div><label>Tipo de contenido</label>
              <select value={ctype} onChange={(e) => setCtype(e.target.value)}>
                <option value="auto">General</option><option value="reality">Reality (Casa de Alofoke)</option><option value="juego">Juegos</option>
                <option value="gta">GTA 5 acción</option><option value="gta_rp">GTA RP (roleplay)</option><option value="directo">Directo (charla)</option>
                <option value="podcast">Podcast</option><option value="entrevista">Entrevista</option>
              </select></div>
            <div><label>Clips nuevos por revisión (máx.)</label>
              <select name="max_new" defaultValue="3"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="5">5</option><option value="8">8</option></select></div>
          </div>
          {ctype === "juego" && <input name="game" placeholder="¿Qué juego es? (ej. Valorant, Fortnite, GTA)" maxLength={60} style={{ marginTop: 10 }} />}
          <label style={{ display: "flex", gap: 8, alignItems: "center", textTransform: "none", fontSize: 13, color: "var(--text)", margin: "12px 0 0" }}>
            <input type="checkbox" name="bar" style={{ width: "auto" }} /> Barra de progreso abajo del clip
          </label>

          <div style={{ marginTop: 16 }}><button className="btn" disabled={busy}>{busy ? "Conectando…" : "Empezar a grabar"}</button></div>
        </form>
      )}

      {source && (
        <div className="grid2">
          <div className="card red">
            <Ring time={fmtTime(p.recorded_sec ?? 0)} label={active ? "EN VIVO" : source.status === "error" ? "ERROR" : "TERMINADO"} />
            <p className="sub" style={{ textAlign: "center", margin: "0 0 4px" }}>{source.title ?? source.url}</p>
            {active && (p.reconnects || p.chat_msgs || p.state === "reconnecting") ? (
              <p className="sub" style={{ textAlign: "center", fontSize: 12, margin: "2px 0 0" }}>
                {p.state === "reconnecting" ? "↻ Reconectando con el directo… " : ""}
                {p.reconnects ? `Reconexiones: ${p.reconnects} · ` : ""}
                {p.chat_msgs ? `Chat leído: ${p.chat_msgs} mensajes` : ""}
              </p>
            ) : null}
            {source.status === "error" && <div className="banner" style={{ marginTop: 12 }}><b>Falló:</b> {source.error}</div>}
            <div className="steps">
              {buildSteps(source, clips.length).map((s) => (
                <div key={s.label} className={`step ${s.state}`}>
                  <i className="dot" />
                  <div><b>{s.label}</b>{s.detail && <span>{s.detail}</span>}</div>
                </div>
              ))}
            </div>
            <div className="why">
              <h4>Por qué no se eligieron</h4>
              {rejected.length === 0 ? (
                <span style={{ color: "var(--muted)" }}>Todavía nada descartado.</span>
              ) : (
                <ul>{rejected.map((r, i) => <li key={i}>{r.title} · {r.score}<span>{r.reason}</span></li>)}</ul>
              )}
            </div>
            {active && (
              <div style={{ marginTop: 14 }}>
                <button className="btn sm" onClick={clipNow} disabled={busy || source.status !== "recording"}>✂ Clip ahora</button>{" "}
                <button className="btn sm ghost" onClick={stop} disabled={busy}>■ Parar</button>
                {!!p.pending_now && <span style={{ marginLeft: 10, fontSize: 12, color: "var(--muted)" }}>{p.pending_now} clip(s) en camino…</span>}
                {nowMsg && <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>{nowMsg}</div>}
              </div>
            )}
          </div>

          <div className="card neon">
            <h4 style={{ fontSize: 14, color: "var(--muted)" }}>Clips de este directo · {clips.length}</h4>
            {clips.length === 0 && <p className="sub" style={{ marginTop: 12 }}>Los clips aparecen aquí cuando la IA los encuentra (después de la primera revisión).</p>}
            <div className="clips" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
              {clips.map((c) => <ClipCard key={c.id} clip={c} />)}
            </div>
          </div>
        </div>
      )}

      <WatchChannels />
    </>
  );
}
