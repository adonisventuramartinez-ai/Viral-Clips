"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { Clip } from "@/lib/types";

export default function EditorIndex() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [err, setErr] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/clips", { cache: "no-store" });
        const j = await r.json();
        if (!alive) return;
        if (!r.ok) throw new Error(j.error || "No se pudo cargar");
        setClips(j.clips || []);
      } catch (e: any) {
        if (alive) setErr(e?.message || "Error de conexión");
      } finally {
        if (alive) setLoaded(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  const list = clips.filter((c) => !q || (c.title || "").toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 18 }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h1 style={{ fontSize: 24, margin: 0 }}>🎬 Editor de clips</h1>
          <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>Recorta, cambia el encuadre, edita el texto y crea miniaturas A/B.</p>
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar un clip…" style={{ maxWidth: 280 }} />
      </div>

      {err && <div className="banner" style={{ marginBottom: 14 }}>⚠ {err}</div>}
      {!loaded && <p style={{ color: "var(--muted)" }}>Cargando clips…</p>}
      {loaded && !err && !list.length && (
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 40 }}>📭</div>
          <p style={{ color: "var(--muted)", margin: "10px 0" }}>{q ? "Ningún clip coincide con la búsqueda." : "Todavía no hay clips. Crea uno primero."}</p>
          <Link className="btn" href="/crear">Crear mi primer clip</Link>
        </div>
      )}

      <div className="grid3">
        {list.map((c) => (
          <Link key={c.id} className="card" href={`/editor/${c.id}`} style={{ display: "block", overflow: "hidden" }}>
            <div style={{ background: "#000", aspectRatio: "16/9", display: "grid", placeItems: "center", position: "relative" }}>
              {c.thumbUrl ? <img src={c.thumbUrl} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : c.videoUrl ? <video src={c.videoUrl} preload="metadata" style={{ width: "100%", height: "100%", objectFit: "cover" }} muted />
                : <span style={{ color: "var(--muted2)", fontSize: 12 }}>Sin vista previa</span>}
              <span style={{ position: "absolute", bottom: 8, right: 8, background: "rgba(0,0,0,.7)", padding: "3px 8px", borderRadius: 6, fontSize: 11 }}>{c.seconds ? `${c.seconds}s` : `${c.start}–${c.end}`}</span>
            </div>
            <div style={{ padding: 12 }}>
              <b style={{ fontSize: 14, display: "block", lineHeight: 1.3 }}>{c.title}</b>
              <small style={{ color: "var(--muted)" }}>{c.score}% viral · Editar →</small>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
