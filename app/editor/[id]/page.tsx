"use client";
import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import Link from "next/link";

type EditorClip = {
  id: string;
  title: string;
  start_sec: number;
  end_sec: number;
  viral_score?: number | null;
  description?: string | null;
  hashtags?: string[] | null;
  storage_path?: string | null;
  sourceKind?: string | null;
  sourceTitle?: string | null;
  videoUrl?: string | null;
  downloadUrl?: string | null;
  thumbUrl?: string | null;
  thumbBUrl?: string | null;
  thumb_choice?: "a" | "b" | null;
  viral_status?: "pending" | "ready" | "review" | "rejected" | "approved" | null;
  scheduled_at?: string | null;
  publish_status?: "scheduled" | "published" | "error" | null;
  viral?: { hook_score?: number; thumb_text?: string } | null;
  captions?: Word[] | string | null;
};

type Tab = "recorte" | "transcripcion" | "encuadre" | "texto" | "miniatura" | "publicar";
type Word = { w?: string; start?: number; end?: number; spk?: number };

const LAYOUTS = [
  { id: "crop", icon: "▣", label: "Vertical", hint: "Llena la pantalla 9:16" },
  { id: "casa", icon: "🏠", label: "La Casa", hint: "Cara grande arriba, fondo difuminado abajo" },
  { id: "split", icon: "◫", label: "Split", hint: "Original arriba, recorte abajo" },
  { id: "split_eq", icon: "◧", label: "Split 50/50", hint: "Dos mitades iguales" },
  { id: "split_game", icon: "◪", label: "Gaming", hint: "Cara + pantalla de juego" },
  { id: "blur", icon: "▤", label: "Difuminado", hint: "Fondo borroso, centro limpio" },
  { id: "duo", icon: "◱", label: "Dúo", hint: "Dos caras lado a lado" },
];
const STYLES = ["rojo", "blanco", "negro", "amarillo", "centro", "arriba"];
const fmt = (s: number) => {
  if (!Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
};
const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));

export default function EditorPage({ params }: { params: { id: string } }) {
  const [clip, setClip] = useState<EditorClip | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("recorte");
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(60);
  const [duration, setDuration] = useState(60);
  const [current, setCurrent] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [layout, setLayout] = useState("crop");
  const [hook, setHook] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [thumbText, setThumbText] = useState("");
  const [thumbStyle, setThumbStyle] = useState("rojo");
  const [frame, setFrame] = useState<string | null>(null);
  const [saved, setSaved] = useState({ title: "", description: "", tags: "", hook: "", layout: "crop", start: 0, end: 60 });
  const [thumbChoice, setThumbChoice] = useState<"a" | "b" | null>(null);
  const [when, setWhen] = useState("");
  const [pubStatus, setPubStatus] = useState<string>("pending");
  const [quality, setQuality] = useState("1080p");
  const [narrate, setNarrate] = useState(false);
  const [drag, setDrag] = useState<"start" | "end" | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);
  const timeline = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`/api/clips/${params.id}`, { cache: "no-store" });
        const j = await r.json();
        if (!alive) return;
        if (!r.ok) throw new Error(j.error || "No se pudo cargar el clip");
        const c: EditorClip = j.clip;
        setClip(c);
        setStart(Number(c.start_sec) || 0);
        setEnd(Number(c.end_sec) || 60);
        setTitle(c.title || "");
        setDescription(c.description || "");
        setTags((c.hashtags || []).join(" "));
        const h = c.viral?.thumb_text || "";
        setHook(h);
        setThumbText(h);
        setSaved({ title: c.title || "", description: c.description || "", tags: (c.hashtags || []).join(" "), hook: h, layout: "crop", start: Number(c.start_sec) || 0, end: Number(c.end_sec) || 60 });
        setThumbChoice(c.thumb_choice ?? null);
        setPubStatus(c.viral_status || c.publish_status || "pending");
        setWhen(c.scheduled_at ? String(c.scheduled_at).slice(0, 16) : "");
        if (c.videoUrl) setError("");
        else setError("Este clip no tiene archivo de video. Espera a que el worker lo termine.");
      } catch (e: any) {
        if (alive) setError(e?.message || "Error de conexión");
      }
    })();
    return () => { alive = false; };
  }, [params.id]);

  /** Actualiza solo los datos del clip (miniaturas, estados) sin tocar lo que estás editando. */
  const refresh = useCallback(async () => {
    try {
      const r = await fetch(`/api/clips/${params.id}`, { cache: "no-store" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.clip) return;
      const c: EditorClip = j.clip;
      setClip((old) => (old ? { ...old, ...c } : c));
      setThumbChoice(c.thumb_choice ?? null);
      setPubStatus(c.viral_status || c.publish_status || "pending");
      setWhen(c.scheduled_at ? String(c.scheduled_at).slice(0, 16) : "");
    } catch { /* silencioso: el editor sigue funcionando con lo que ya tenía */ }
  }, [params.id]);

  const seek = useCallback((t: number) => {
    const v = video.current;
    if (!v || !Number.isFinite(t)) return;
    v.currentTime = clamp(t, 0, duration || 0);
    setCurrent(v.currentTime);
  }, [duration]);

  const togglePlay = useCallback(() => {
    const v = video.current;
    if (!v) return;
    if (v.paused) { v.play().catch(() => {}); setPlaying(true); }
    else { v.pause(); setPlaying(false); }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && /INPUT|TEXTAREA|SELECT/.test(t.tagName)) return;
      if (e.code === "Space") { e.preventDefault(); togglePlay(); }
      else if (e.key.toLowerCase() === "i") setStart(clamp(current, 0, Math.max(0, end - 5)));
      else if (e.key.toLowerCase() === "o") setEnd(clamp(current, start + 5, duration || current + 5));
      else if (e.key === "ArrowLeft") { e.preventDefault(); seek(current - (e.shiftKey ? 5 : 1)); }
      else if (e.key === "ArrowRight") { e.preventDefault(); seek(current + (e.shiftKey ? 5 : 1)); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, duration, end, seek, start, togglePlay]);

  function setStartSafe(v: number) { setStart(clamp(v, 0, Math.max(0, end - 5))); }
  function setEndSafe(v: number) { setEnd(clamp(v, Math.min(duration, start + 5), duration)); }

  function timeAt(clientX: number): number {
    const el = timeline.current;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    return clamp(((clientX - r.left) / Math.max(1, r.width)) * duration, 0, duration);
  }
  function dragTo(clientX: number, which: "start" | "end") {
    const t = timeAt(clientX);
    if (which === "start") setStartSafe(t);
    else setEndSafe(t);
  }
  function onTimelineDown(e: ReactPointerEvent<HTMLDivElement>) {
    const t = timeAt(e.clientX);
    const which = Math.abs(t - start) <= Math.abs(t - end) ? "start" : "end";
    setDrag(which);
    dragTo(e.clientX, which);
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* navegador antiguo */ }
  }

  function applyLength(sec: number) {
    const s = start;
    const e = Math.min(duration, s + sec);
    if (e - s < 5) { setNote({ ok: false, text: "El inicio está muy al final del video para ese largo" }); return; }
    setEnd(e);
    seek(e - 0.1);
  }

  function capture(): string | null {
    const v = video.current;
    if (!v || !v.videoWidth) return null;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = Math.min(720, v.videoWidth);
      canvas.height = Math.round(canvas.width * (v.videoHeight / v.videoWidth));
      const ctx = canvas.getContext("2d");
      if (!ctx) return null;
      ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
      const url = canvas.toDataURL("image/jpeg", 0.82);
      setFrame(url);
      return url;
    } catch {
      setNote({ ok: false, text: "El navegador no permite capturar este video; el worker igual puede hacer la miniatura." });
      return null;
    }
  }

  async function postViral(body: Record<string, unknown>): Promise<boolean> {
    try {
      const r = await fetch("/api/viral", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { setNote({ ok: false, text: j.error || "No se pudo guardar" }); return false; }
      return true;
    } catch {
      setNote({ ok: false, text: "Sin conexión con el servidor" });
      return false;
    }
  }

  async function saveMeta(silent = false): Promise<boolean> {
    if (!clip) return false;
    if (title.trim().length < 3) { setNote({ ok: false, text: "El título necesita al menos 3 letras" }); return false; }
    const ok = await postViral({
      action: "edit", id: clip.id, title, description,
      hashtags: tags.split(/\s+/).filter(Boolean), hook,
    });
    if (!ok) return false;
    setSaved((s) => ({ ...s, title, description, tags, hook }));
    if (!silent) setNote({ ok: true, text: "Borrador guardado. El video no se ha tocado." });
    return true;
  }

  async function saveDraft() {
    if (!metaDirty) { setNote({ ok: true, text: "No hay cambios de texto que guardar." }); return; }
    setBusy(true); setNote(null);
    await saveMeta();
    setBusy(false);
  }

  async function renderChanges() {
    if (!clip) return;
    if (end - start < 5 || end - start > 180) { setNote({ ok: false, text: "El clip debe durar entre 5 y 180 segundos" }); return; }
    if (!metaDirty && !needsRender) { setNote({ ok: true, text: "No hay cambios pendientes." }); return; }
    setBusy(true); setNote(null);
    if (metaDirty && !(await saveMeta(true))) { setBusy(false); return; }
    if (clip.sourceKind === "live") {
      setNote({ ok: true, text: "Texto guardado. Los clips de directo no se pueden renderizar otra vez (el directo ya pasó)." });
      setBusy(false);
      return;
    }
    if (!clip.videoUrl) {
      setNote({ ok: false, text: "Este clip todavía no tiene video. Espera a que el worker lo termine." });
      setBusy(false);
      return;
    }
    try {
      const r = await fetch(`/api/clips/${clip.id}/rerender`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start: Math.round(start * 10) / 10, end: Math.round(end * 10) / 10,
          layout, hook: hook || undefined, quality, narrate,
        }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || "No se pudo pedir el render");
      setSaved({ title, description, tags, hook, layout, start, end });
      setNote({ ok: true, text: "En cola. El worker está renderizando la nueva versión con tus cambios." });
    } catch (e: any) {
      setNote({ ok: false, text: e?.message || "Error inesperado" });
    }
    setBusy(false);
  }

  async function thumbs(slot: "a" | "b") {
    if (!clip) return;
    setBusy(true); setNote(null);
    capture();
    const ok = await postViral({
      action: "thumbs", id: clip.id,
      [slot]: { text: thumbText || title.slice(0, 24), style: thumbStyle, time: Math.round(current * 10) / 10 },
    });
    if (ok) {
      setNote({ ok: true, text: `Miniatura ${slot.toUpperCase()} en cola. Pulsa Actualizar en unos segundos.` });
      window.setTimeout(() => { void refresh(); }, 2500);
    }
    setBusy(false);
  }

  async function chooseThumb(slot: "a" | "b") {
    if (!clip) return;
    setBusy(true); setNote(null);
    if (await postViral({ action: "choose_thumb", id: clip.id, choice: slot })) {
      setThumbChoice(slot);
      setNote({ ok: true, text: `Miniatura ${slot.toUpperCase()} elegida para publicar.` });
      await refresh();
    }
    setBusy(false);
  }

  async function viralAction(action: "approve" | "reject" | "reopen") {
    if (!clip) return;
    setBusy(true); setNote(null);
    const labels = { approve: "aprobado", reject: "descartado", reopen: "en revisión" };
    if (await postViral({ action, id: clip.id })) {
      setNote({ ok: true, text: `Clip ${labels[action]}.` });
      await refresh();
    }
    setBusy(false);
  }

  async function changeSchedule(iso: string | null) {
    if (!clip) return;
    setBusy(true); setNote(null);
    try {
      const r = await fetch(`/api/clips/${clip.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_at: iso }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || "No se pudo programar");
      setNote({ ok: true, text: iso ? "Publicación programada." : "Programación cancelada." });
      await refresh();
    } catch (e: any) {
      setNote({ ok: false, text: e?.message || "Error inesperado" });
    }
    setBusy(false);
  }

  async function bestSlot() {
    if (!clip) return;
    setBusy(true); setNote(null);
    try {
      const r = await fetch(`/api/clips/${clip.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_slot: true }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || "No hay horas libres");
      setNote({ ok: true, text: "Programado en la mejor hora libre y aprobado." });
      await refresh();
    } catch (e: any) {
      setNote({ ok: false, text: e?.message || "Error inesperado" });
    }
    setBusy(false);
  }

  const metaDirty = title !== saved.title || description !== saved.description || tags !== saved.tags || hook !== saved.hook;
  const cutDirty = start !== saved.start || end !== saved.end || layout !== saved.layout;
  const needsRender = cutDirty || hook !== saved.hook;

  if (error && !clip) return (
    <div className="page"><div className="card">
      <h2>No se pudo abrir el editor</h2><p style={{ color: "var(--muted)" }}>{error}</p>
      <Link className="btn ghost sm" href="/biblioteca">← Volver a la biblioteca</Link>
    </div></div>
  );
  if (!clip) return <div className="page"><p style={{ color: "var(--muted)" }}>Cargando editor…</p></div>;

  const len = Math.max(0, end - start);
  const disabledRender = clip.sourceKind === "live" || !clip.videoUrl;

  return (
    <div className="page" style={{ maxWidth: 1440 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 18 }}>
        <Link className="btn ghost sm" href="/biblioteca">← Biblioteca</Link>
        <div style={{ minWidth: 220, flex: 1 }}>
          <h1 style={{ fontSize: 22, margin: 0 }}>Editor de clip</h1>
          <p style={{ color: "var(--muted)", margin: "2px 0 0", fontSize: 13 }}>
            {clip.sourceTitle || clip.title} · {fmt(len)} · {clip.viral_score ?? "—"}%
          </p>
        </div>
        <span className="pill ghost">{clip.sourceKind === "live" ? "Directo" : "Video"}</span>
        {(metaDirty || needsRender) && <span className="pill" style={{ fontSize: 11 }}>Cambios sin guardar</span>}
        {clip.downloadUrl && <a className="btn ghost sm" href={clip.downloadUrl} target="_blank" rel="noreferrer">⬇ Descargar</a>}
        <button className="btn ghost sm" disabled={busy || !metaDirty} onClick={saveDraft}>💾 Guardar borrador</button>
        <button className="btn" disabled={busy || disabledRender || !needsRender} onClick={renderChanges}>{busy ? "Trabajando…" : "🎞 Renderizar cambios"}</button>
      </div>

      {note && <div className="card" style={{ borderColor: note.ok ? "rgba(16,185,129,.5)" : "rgba(244,63,94,.5)", marginBottom: 14, padding: "10px 14px" }}>
        <span style={{ color: note.ok ? "var(--emerald2)" : "var(--red2)" }}>{note.ok ? "✓" : "⚠"}</span> {note.text}
      </div>}

      <div className="editor-grid">
        <div>
          <div className="card" style={{ padding: 12 }}>
            <div style={{ position: "relative", background: "#000", borderRadius: 12, overflow: "hidden", display: "grid", placeItems: "center" }}>
              {clip.videoUrl ? (
                <div style={{ position: "relative", display: "inline-block", lineHeight: 0 }}>
                  <video ref={video} src={clip.videoUrl} poster={clip.thumbUrl || undefined} controls playsInline preload="metadata"
                    style={{ width: "100%", maxHeight: "62vh", objectFit: "contain", display: "block" }}
                    onLoadedMetadata={(e) => {
                      const d = e.currentTarget.duration || 60;
                      const s = clamp(Number(clip.start_sec) || 0, 0, Math.max(0, d - 5));
                      setDuration(d); setStart(s);
                      setEnd((v) => clamp(v || d, s + 5, d));
                      setSaved((v) => ({ ...v, start: s, end: clamp(v.end || d, s + 5, d) }));
                    }}
                    onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
                    onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} />
                  <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
                    {layout.startsWith("split") && <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 2, background: "rgba(255,255,255,.72)", boxShadow: "0 0 8px rgba(0,0,0,.8)" }} />}
                    {layout === "duo" && <div style={{ position: "absolute", top: 0, bottom: 0, left: "50%", width: 2, background: "rgba(255,255,255,.72)", boxShadow: "0 0 8px rgba(0,0,0,.8)" }} />}
                    {layout === "crop" && <div style={{ position: "absolute", left: "35%", right: "35%", top: 0, bottom: 0, borderLeft: "1px dashed rgba(34,211,238,.7)", borderRight: "1px dashed rgba(34,211,238,.7)" }} />}
                    {layout === "blur" && <div style={{ position: "absolute", left: "25%", right: "25%", top: "10%", bottom: "10%", border: "1px dashed rgba(34,211,238,.7)", borderRadius: 12 }} />}
                    {hook && <div style={{ position: "absolute", top: "6%", left: "6%", right: "6%", textAlign: "center" }}>
                      <span style={{ background: "rgba(0,0,0,.55)", color: "#fff", fontWeight: 800, fontSize: "clamp(15px, 2.5vw, 26px)", padding: "6px 14px", borderRadius: 10, textShadow: "0 2px 8px #000" }}>{hook.slice(0, 70)}</span>
                    </div>}
                    <span style={{ position: "absolute", bottom: 8, left: 8, background: "rgba(0,0,0,.65)", color: "#fff", fontSize: 11, padding: "4px 8px", borderRadius: 6 }}>
                      {LAYOUTS.find((l) => l.id === layout)?.label || "Vertical"} · vista previa
                    </span>
                  </div>
                </div>
              ) : <div style={{ aspectRatio: "9/16", maxHeight: "55vh", display: "grid", placeItems: "center", color: "var(--muted)" }}>Sin video disponible</div>}
            </div>

            <div style={{ marginTop: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--muted)", marginBottom: 6 }}>
                <span>Línea de tiempo · <b style={{ color: "var(--text)" }}>{fmt(current)}</b> / {fmt(duration)}</span>
                <span>Selección: {fmt(start)} → {fmt(end)} ({fmt(len)})</span>
              </div>
              <div ref={timeline} role="slider" tabIndex={0} aria-label="Línea de tiempo: arrastra para mover el inicio o el fin"
                aria-valuemin={0} aria-valuemax={Math.round(duration)} aria-valuenow={Math.round(current)}
                onPointerDown={onTimelineDown}
                onPointerMove={(e) => { if (drag) dragTo(e.clientX, drag); }}
                onPointerUp={() => setDrag(null)} onPointerCancel={() => setDrag(null)}
                style={{ position: "relative", height: 38, borderRadius: 8, background: "linear-gradient(90deg,#0b1022,#131d3a)", border: "1px solid var(--line)", overflow: "hidden", cursor: "ew-resize", touchAction: "none" }}>
                <div style={{ position: "absolute", top: 0, bottom: 0, left: `${(start / (duration || 1)) * 100}%`, width: `${(len / (duration || 1)) * 100}%`, background: "linear-gradient(90deg,rgba(99,102,241,.55),rgba(34,211,238,.4))" }} />
                <div className="editor-handle" style={{ left: `${(start / (duration || 1)) * 100}%`, background: "var(--cyan2)" }} />
                <div className="editor-handle" style={{ left: `${(end / (duration || 1)) * 100}%`, background: "var(--red2)" }} />
                <div style={{ position: "absolute", top: 0, bottom: 0, left: `${(current / (duration || 1)) * 100}%`, width: 2, background: "#fff", boxShadow: "0 0 8px #fff" }} />
              </div>
              <div className="row" style={{ gridTemplateColumns: "repeat(2, 1fr)", marginTop: 10 }}>
                <label>Inicio <input type="number" min={0} max={Math.max(0, end - 5)} step={0.1} value={Number(start.toFixed(1))} onChange={(e) => setStartSafe(Number(e.target.value))} /></label>
                <label>Fin <input type="number" min={start + 5} max={duration} step={0.1} value={Number(end.toFixed(1))} onChange={(e) => setEndSafe(Number(e.target.value))} /></label>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
                {[15, 30, 45, 60].map((s) => <button key={s} className="btn ghost sm" onClick={() => applyLength(s)}>{s}s</button>)}
                <button className="btn ghost sm" onClick={() => { setStartSafe(current); seek(current); }}>I · Marcar inicio</button>
                <button className="btn ghost sm" onClick={() => { setEndSafe(current); seek(current); }}>O · Marcar fin</button>
                <button className="btn ghost sm" onClick={togglePlay}>{playing ? "⏸ Pausa" : "▶ Reproducir"}</button>
              </div>
              <p style={{ color: "var(--muted2)", fontSize: 11, marginTop: 8 }}>Atajos: Espacio reproducir · I inicio · O fin · ←/→ mover 1s (Shift 5s)</p>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 16 }}>
            {(["recorte", "transcripcion", "encuadre", "texto", "miniatura", "publicar"] as Tab[]).map((t) => (
              <button key={t} className={`btn sm ${tab === t ? "" : "ghost"}`} onClick={() => setTab(t)}>
                {t === "recorte" ? "✂ Recorte" : t === "transcripcion" ? "💬 Transcripción" : t === "encuadre" ? "▣ Encuadre" : t === "texto" ? "✎ Texto" : t === "miniatura" ? "🖼 Miniatura" : "🚀 Publicar"}
              </button>
            ))}
          </div>

          {tab === "recorte" && (
            <div>
              <h3 style={{ fontSize: 16 }}>Puntos de corte</h3>
              <p style={{ color: "var(--muted)", fontSize: 13 }}>Arrastra los tiradores de la línea de tiempo o usa los atajos I/O. Después pulsa <b>Renderizar cambios</b>.</p>
              <div className="row" style={{ gridTemplateColumns: "repeat(2, 1fr)", marginTop: 14 }}>
                <button className="btn ghost sm" onClick={() => seek(start)}>Ir al inicio</button>
                <button className="btn ghost sm" onClick={() => seek(Math.max(0, end - 0.5))}>Ir al fin</button>
              </div>
              <div style={{ marginTop: 16, padding: 12, borderRadius: 10, background: "var(--glass)", border: "1px solid var(--glass-border)" }}>
                <b style={{ fontSize: 13 }}>Duración final:</b> <span style={{ color: "var(--cyan2)" }}>{fmt(len)}</span>
                <p style={{ color: "var(--muted2)", fontSize: 11, marginTop: 4 }}>Entre 5 y 180 s. El worker ajusta el corte a pausas naturales.</p>
              </div>
            </div>
          )}

          {tab === "transcripcion" && (() => {
            const words: Word[] = Array.isArray(clip.captions) ? clip.captions : [];
            if (!words.length) return (
              <div>
                <h3 style={{ fontSize: 16 }}>Transcripción</h3>
                <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 8 }}>
                  Este clip no trae transcripción guardada. Usa el reproductor y los atajos I/O para marcar los cortes.
                </p>
              </div>
            );
            let lastSpk = -99;
            return (
              <div>
                <h3 style={{ fontSize: 16 }}>Edita por palabras</h3>
                <p style={{ color: "var(--muted)", fontSize: 13 }}>
                  Toca una palabra para saltar a ese momento. Luego pulsa <b>I</b> para marcar el inicio o <b>O</b> para el fin.
                </p>
                <div style={{ marginTop: 12, maxHeight: 420, overflowY: "auto", padding: 12, borderRadius: 10, background: "var(--glass)", border: "1px solid var(--glass-border)", lineHeight: 2 }}>
                  {words.map((w, i) => {
                    const spk = Number(w.spk ?? 0);
                    const head = spk !== lastSpk;
                    lastSpk = spk;
                    return (
                      <span key={i}>
                        {head && <div style={{ margin: "10px 0 2px", color: spk === 0 ? "var(--cyan2)" : "var(--orange)", fontSize: 11, fontWeight: 700 }}>P{spk + 1}</div>}
                        <button onClick={() => seek(Number(w.start ?? 0))} title={`${fmt(Number(w.start ?? 0))} · toca para ir aquí`}
                          style={{ background: "transparent", border: 0, color: "var(--text)", cursor: "pointer", padding: "1px 2px", borderRadius: 4 }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(99,102,241,.25)"; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
                          {w.w}{" "}
                        </button>
                      </span>
                    );
                  })}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  <button className="btn ghost sm" onClick={() => setStartSafe(current)}>Marcar inicio aquí</button>
                  <button className="btn ghost sm" onClick={() => setEndSafe(current)}>Marcar fin aquí</button>
                </div>
              </div>
            );
          })()}

          {tab === "encuadre" && (
            <div>
              <h3 style={{ fontSize: 16 }}>Encuadre</h3>
              <p style={{ color: "var(--muted)", fontSize: 13 }}>Elige cómo se ve el video original dentro del formato vertical.</p>
              <div className="grid3" style={{ gridTemplateColumns: "repeat(2, 1fr)", marginTop: 14 }}>
                {LAYOUTS.map((l) => (
                  <button key={l.id} onClick={() => setLayout(l.id)} className="btn ghost sm"
                    style={{ textAlign: "left", padding: 12, borderColor: layout === l.id ? "var(--cyan)" : undefined, background: layout === l.id ? "rgba(34,211,238,.12)" : undefined }}>
                    <div style={{ fontSize: 22 }}>{l.icon}</div>
                    <b>{l.label}</b><div style={{ color: "var(--muted2)", fontSize: 11 }}>{l.hint}</div>
                  </button>
                ))}
              </div>
              <div className="row" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
                <label>Calidad <select value={quality} onChange={(e) => setQuality(e.target.value)}>
                  {["720p", "1080p", "1440p", "2160p"].map((q) => <option key={q} value={q}>{q}</option>)}
                </select></label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, textTransform: "none", letterSpacing: 0 }}>
                  <input type="checkbox" checked={narrate} onChange={(e) => setNarrate(e.target.checked)} style={{ width: 18, height: 18 }} />
                  Voz narradora
                </label>
              </div>
              <p style={{ color: "var(--muted2)", fontSize: 11, marginTop: 8 }}>La guía sobre el video muestra cómo quedará el encuadre al renderizar.</p>
            </div>
          )}

          {tab === "texto" && (
            <div style={{ display: "grid", gap: 12 }}>
              <div>
                <h3 style={{ fontSize: 16 }}>Texto y publicación</h3>
                <p style={{ color: "var(--muted)", fontSize: 13 }}>Se guarda en el clip y se usa en el paquete de TikTok, Reels y Shorts.</p>
              </div>
              <label>Título <input value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} placeholder="Título del clip" /></label>
              <label>Gancho en pantalla <input value={hook} maxLength={70} onChange={(e) => setHook(e.target.value)} placeholder="¡MIRA ESTO!" /><small style={{ color: "var(--muted2)" }}>{hook.length}/70 · aparece arriba en la vista previa</small></label>
              <label>Descripción <textarea value={description} rows={3} maxLength={2200} onChange={(e) => setDescription(e.target.value)} placeholder="Texto para la publicación" /></label>
              <label>Hashtags <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="#viral #fyp #alofoke" /></label>
            </div>
          )}

          {tab === "miniatura" && (
            <div>
              <h3 style={{ fontSize: 16 }}>Miniatura A/B</h3>
              <p style={{ color: "var(--muted)", fontSize: 13 }}>Pausa en el cuadro que quieras, escribe el texto y pide la miniatura. El worker la genera en segundos.</p>
              <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap", margin: "14px 0" }}>
                <div style={{ borderRadius: 10, overflow: "hidden", border: "1px solid var(--line)", background: "#000", aspectRatio: "9/16", width: 180 }}>
                  {frame ? <img src={frame} alt="Cuadro capturado" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    : <div style={{ height: "100%", display: "grid", placeItems: "center", color: "var(--muted2)", fontSize: 12, textAlign: "center", padding: 10 }}>Pausa y captura un cuadro</div>}
                </div>
                <div style={{ flex: 1, minWidth: 220, display: "grid", gap: 10 }}>
                  <label>Texto <input value={thumbText} maxLength={40} onChange={(e) => setThumbText(e.target.value)} placeholder="¿LO VISTE?" /></label>
                  <label>Estilo <select value={thumbStyle} onChange={(e) => setThumbStyle(e.target.value)}>{STYLES.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
                  <p style={{ color: "var(--muted2)", fontSize: 12 }}>Cuadro actual: <b style={{ color: "var(--text)" }}>{fmt(current)}</b></p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="btn ghost sm" disabled={busy} onClick={() => capture()}>📸 Capturar</button>
                    <button className="btn ghost sm" disabled={busy} onClick={() => thumbs("a")}>Pedir A</button>
                    <button className="btn ghost sm" disabled={busy} onClick={() => thumbs("b")}>Pedir B</button>
                    <button className="btn ghost sm" disabled={busy} onClick={() => { void refresh(); }}>🔄 Actualizar</button>
                  </div>
                </div>
              </div>
              <div className="grid2" style={{ gridTemplateColumns: "1fr 1fr" }}>
                {(["a", "b"] as const).map((slot) => {
                  const url = slot === "a" ? clip.thumbUrl : clip.thumbBUrl;
                  const chosen = slot === "a" ? thumbChoice !== "b" : thumbChoice === "b";
                  return (
                    <div key={slot} className="card" style={{ padding: 10, borderColor: chosen ? "var(--cyan)" : undefined }}>
                      <div style={{ aspectRatio: "9/16", background: "#000", borderRadius: 8, overflow: "hidden", display: "grid", placeItems: "center" }}>
                        {url ? <img src={url} alt={`Miniatura ${slot.toUpperCase()}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                          : <span style={{ color: "var(--muted2)", fontSize: 12 }}>Sin miniatura {slot.toUpperCase()}</span>}
                      </div>
                      <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
                        <b style={{ flex: 1 }}>Miniatura {slot.toUpperCase()}</b>
                        {url && <button className="btn sm ghost" disabled={busy || chosen} onClick={() => chooseThumb(slot)}>{chosen ? "Elegida" : "Usar"}</button>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {tab === "publicar" && (
            <div style={{ display: "grid", gap: 12 }}>
              <div>
                <h3 style={{ fontSize: 16 }}>Publicación</h3>
                <p style={{ color: "var(--muted)", fontSize: 13 }}>Estado actual: <b style={{ color: "var(--cyan2)" }}>{pubStatus}</b>{clip.scheduled_at ? ` · ${new Date(clip.scheduled_at).toLocaleString()}` : ""}</p>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn sm ghost" disabled={busy} onClick={() => viralAction("approve")}>✅ Aprobar</button>
                <button className="btn sm ghost" disabled={busy} onClick={() => viralAction("reopen")}>🔄 En revisión</button>
                <button className="btn sm ghost" disabled={busy} onClick={() => viralAction("reject")}>✖ Descartar</button>
                <button className="btn sm" disabled={busy} onClick={bestSlot}>⚡ Mejor hora</button>
              </div>
              <label>Fecha y hora <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></label>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn sm" disabled={busy || !when} onClick={() => changeSchedule(new Date(when).toISOString())}>📅 Programar</button>
                <button className="btn sm ghost" disabled={busy || !clip.scheduled_at} onClick={() => changeSchedule(null)}>Cancelar programación</button>
              </div>
              <p style={{ color: "var(--muted2)", fontSize: 11 }}>La mejor hora elige el próximo hueco libre aprendido de Facebook. Puedes programar entre 1 minuto y 60 días.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
