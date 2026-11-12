"use client";
import { useEffect, useRef, useState } from "react";
import ClipCard from "@/components/ClipCard";
import { ACTIVE, STATUS_LABEL } from "@/lib/format";
import type { Clip, SourceRow } from "@/lib/types";

export default function Biblioteca() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [demo, setDemo] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [err, setErr] = useState("");
  const [worker, setWorker] = useState<boolean | null>(null);
  const [sort, setSort] = useState<"viral" | "new" | "old">("viral");
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(0);
  const [minScore, setMinScore] = useState(0);
  const [cleaning, setCleaning] = useState(false);
  const [note, setNote] = useState("");
  const reload = useRef<() => void>(() => {});

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;

    async function load() {
      clearTimeout(timer);
      let active = false;
      try {
        const r = await fetch("/api/clips", { cache: "no-store" });
        const j = await r.json();
        if (!alive) return;
        if (!r.ok) {
          setErr(j.error ?? "Error al cargar");
        } else {
          // Mantiene la URL del video ya cargada para que el reproductor no se reinicie al refrescar.
          setClips((prev) =>
            (j.clips as Clip[]).map((c) => {
              const old = prev.find((p) => p.id === c.id);
              return old && old.path === c.path ? { ...c, videoUrl: old.videoUrl ?? c.videoUrl, downloadUrl: old.downloadUrl ?? c.downloadUrl } : c;
            }),
          );
          setSources(j.sources);
          setDemo(!!j.demo);
          setWorker(j.worker ?? null);
          setErr("");
          active = (j.sources as SourceRow[]).some((s) => ACTIVE.includes(s.status)) || (j.editing ?? 0) > 0;
          setEditing(j.editing ?? 0);
        }
      } catch {
        if (alive) setErr("No se pudo conectar con el servidor");
      } finally {
        if (alive) setLoaded(true);
      }
      // Solo vuelve a consultar mientras haya trabajos en proceso.
      if (alive && active) timer = setTimeout(load, 5000);
    }

    reload.current = load;
    load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, []);

  /** Quita una fuente (id) o todas las pegadas/con error (sin id). */
  async function clean(id?: string) {
    if (!id && !confirm("¿Limpiar todo lo que está en cola, con error o detenido?\n\nLos clips ya creados NO se borran.")) return;
    setCleaning(true);
    setNote("");
    try {
      const res = await fetch("/api/sources", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(id ? { id } : {}),
      });
      const j = await res.json();
      if (!res.ok) {
        setErr(j.error ?? "No se pudo limpiar");
      } else {
        const parts = [`${j.removed} quitado(s) (encontré ${j.found ?? 0})`];
        if (j.kept) parts.push(`${j.kept} se conservó porque ya tenía clips`);
        if (j.stopping) parts.push(`${j.stopping} directo(s) en proceso de parar`);
        if (j.more) parts.push("quedan más: vuelve a tocar el botón");
        setNote(parts.join(" · "));
      }
    } catch {
      setErr("No se pudo conectar con el servidor");
    }
    setCleaning(false);
    reload.current();
  }

  const working = sources.filter((s) => ACTIVE.includes(s.status));
  const failed = sources.filter((s) => s.status === "error");
  const stuck = sources.filter((s) => s.status === "queued");
  const cleanable = sources.filter((s) => s.status === "error" || s.status === "stopped" || ACTIVE.includes(s.status));
  const term = q.trim().toLowerCase();
  const filtered = clips.filter((c) => c.score >= minScore && (!term || c.title.toLowerCase().includes(term)));
  const shown = sort === "viral" ? [...filtered].sort((a, b) => b.score - a.score) : sort === "old" ? [...filtered].reverse() : filtered;
  const STEPS = ["queued", "downloading", "transcribing", "analyzing", "clipping"];

  return (
    <>
      <h1>Biblioteca</h1>
      <p className="sub">Todos tus clips guardados.</p>

      {demo && <div className="banner">Supabase no está conectado, no hay clips reales que mostrar.</div>}
      {err && <div className="banner">{err}</div>}
      {note && <div className="banner ok">{note}</div>}
      {editing > 0 && <div className="banner ok">Ajustando {editing} clip(s)… se actualizan solos cuando el worker termine.</div>}
      {worker === false && stuck.length > 0 && (
        <div className="banner">Hay trabajos en cola pero el worker está apagado. Enciéndelo en tu PC (docker run …) y empezará solo.</div>
      )}

      {cleanable.length > 0 && (
        <div style={{ margin: "0 0 14px" }}>
          <button className="btn" onClick={() => clean()} disabled={cleaning}>
            {cleaning ? "Limpiando…" : `🧹 Limpiar cola y errores (${cleanable.length})`}
          </button>
        </div>
      )}

      {working.map((s) => (
        <div key={s.id} className="step active" style={{ marginBottom: 10, justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", minWidth: 0 }}>
            <i className="dot" />
            <div style={{ minWidth: 0 }}>
              <b>{STATUS_LABEL[s.status] ?? s.status}…{STEPS.includes(s.status) ? ` (paso ${STEPS.indexOf(s.status) + 1} de ${STEPS.length})` : ""}</b>
              <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis" }}>{s.title ?? s.url}</span>
            </div>
          </div>
          <button className="btn ghost sm" onClick={() => clean(s.id)} disabled={cleaning}>
            Quitar
          </button>
        </div>
      ))}
      {failed.map((s) => (
        <div key={s.id} className="banner">
          <b>Falló:</b> {s.title ?? s.url}<br />
          <span style={{ color: "var(--muted)", fontSize: 13, wordBreak: "break-word" }}>{s.error}</span>
          <div style={{ marginTop: 8 }}>
            <button className="btn ghost sm" onClick={() => clean(s.id)} disabled={cleaning}>
              Quitar
            </button>
          </div>
        </div>
      ))}

      {clips.length > 0 && (
        <div style={{ margin: "14px 0 0", display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="🔍 Buscar por título…" style={{ maxWidth: 260 }} />
          <select value={sort} onChange={(e) => setSort(e.target.value as "viral" | "new" | "old")} style={{ maxWidth: 220 }}>
            <option value="viral">Más virales primero</option>
            <option value="new">Más recientes primero</option>
            <option value="old">Más antiguos primero</option>
          </select>
          <select value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} style={{ maxWidth: 180 }}>
            <option value={0}>Cualquier score</option>
            <option value={60}>Score 60%+</option>
            <option value={75}>Score 75%+</option>
            <option value={90}>Score 90%+</option>
          </select>
          <small style={{ color: "var(--muted)" }}>{filtered.length} de {clips.length} clips</small>
        </div>
      )}

      <div className="clips">{shown.map((c) => <ClipCard key={c.id} clip={c} onDeleted={(id) => setClips((p) => p.filter((x) => x.id !== id))} onAdjusted={() => reload.current()} />)}</div>

      {loaded && !demo && clips.length === 0 && working.length === 0 && failed.length === 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          Aún no hay clips. Ve a <b>Crear clips</b>, pega un link y toca Analizar video (con el worker encendido).
        </div>
      )}
    </>
  );
}
