"use client";

import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { armarMensaje, sugerirHashtags, sugerirTitulos } from "@/lib/sugerencias";
import type { Tendencia } from "@/lib/tendencias";

interface Theme { cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string; accentText?: string }
interface Cuenta { id: number; nombre: string }
interface Pagina { id: string; name: string }
export interface VideoListo { id: number; titulo: string | null; descripcion: string | null; autor: string | null; archivo_url: string; miniatura: string | null }

export default function PublicarYa({ video, theme, onCerrar, onHecho }: { video: VideoListo; theme: Theme; onCerrar: () => void; onHecho: () => void }) {
  const desc = video.descripcion || video.titulo || "";
  const titulos = useMemo(() => sugerirTitulos(desc, video.autor || ""), [desc, video.autor]);
  const tags = useMemo(() => sugerirHashtags(desc, video.autor || ""), [desc, video.autor]);

  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [cuentaId, setCuentaId] = useState<number | null>(null);
  const [paginas, setPaginas] = useState<Pagina[]>([]);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [tipo, setTipo] = useState<"reel" | "video">("reel");
  const [titulo, setTitulo] = useState(titulos[0] || "");
  const [elegidos, setElegidos] = useState<Set<string>>(new Set(tags.recomendados));
  const [texto, setTexto] = useState(() => (video.descripcion || "").replace(/#[\p{L}\p{N}_]+/gu, "").replace(/\s+/g, " ").trim());
  const [enviando, setEnviando] = useState(false);
  const [tendencias, setTendencias] = useState<Tendencia[] | null>(null);
  const [geo, setGeo] = useState("");

  useEffect(() => {
    fetch("/api/fb/accounts").then((r) => r.json()).then((d) => {
      const c: Cuenta[] = d.cuentas || [];
      setCuentas(c);
      if (c.length) setCuentaId(c[0].id);
    }).catch(() => toast.error("No se pudieron cargar las cuentas"));
  }, []);

  useEffect(() => {
    fetch(`/api/fb/tendencias?desc=${encodeURIComponent(desc.slice(0, 400))}`)
      .then((r) => r.json())
      .then((d) => { setTendencias(d.tendencias || []); setGeo(d.geo || ""); })
      .catch(() => setTendencias([]));
  }, [desc]);

  useEffect(() => {
    setSel(new Set());
    if (!cuentaId) return setPaginas([]);
    fetch(`/api/fb/accounts/${cuentaId}/paginas`).then((r) => r.json()).then((d) => {
      if (d.error) { toast.error(d.error); setPaginas([]); } else {
        const p: Pagina[] = d.paginas || [];
        setPaginas(p);
        if (p.length === 1) setSel(new Set([p[0].id])); // una sola página: ya viene marcada
      }
    }).catch(() => setPaginas([]));
  }, [cuentaId]);

  const mensaje = armarMensaje(texto, [...elegidos]);
  const alternar = (h: string) => setElegidos((s) => { const n = new Set(s); n.has(h) ? n.delete(h) : n.add(h); return n; });

  async function publicar() {
    if (!cuentaId) return toast.error("Selecciona una cuenta");
    if (!sel.size) return toast.error("Marca al menos una página");
    setEnviando(true);
    try {
      const r = await fetch("/api/fb/schedule/lote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ahora: true, cuenta_id: cuentaId, tipo,
          paginas: paginas.filter((p) => sel.has(p.id)).map((p) => ({ id: p.id, name: p.name })),
          items: [{ importacion_id: video.id, archivo_url: video.archivo_url, archivo_nombre: (video.titulo || `Video ${video.id}`).slice(0, 80), titulo, mensaje }],
        }),
      });
      const d = await r.json();
      if (!r.ok || d.error) throw new Error(d.error || "No se pudo publicar");
      if (d.publicacion && !d.publicacion.ok) toast(d.publicacion.error, { icon: "⚠️", duration: 9000 });
      else toast.success("🚀 Enviado a publicar. En unos segundos aparece en Historial.", { duration: 6000 });
      onHecho();
      onCerrar();
    } catch (e: any) {
      toast.error(e.message || "Error al publicar");
    } finally {
      setEnviando(false);
    }
  }

  const campo = { width: "100%", padding: 8, borderRadius: 6, border: `1px solid ${theme.border}`, background: theme.cardBg, color: theme.text, boxSizing: "border-box" } as const;
  const chip = (on: boolean) => ({ border: `1px solid ${on ? theme.accent : theme.border}`, background: on ? theme.accent : "none", color: on ? theme.accentText || "#fff" : theme.text, borderRadius: 999, padding: "3px 10px", fontSize: 12, cursor: "pointer" }) as const;
  const etiqueta = { fontSize: 12, fontWeight: 600, margin: "14px 0 6px", display: "block" } as const;

  return (
    <div onClick={onCerrar} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.6)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: 12 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: theme.formBg, color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 12, width: "100%", maxWidth: 560, maxHeight: "92vh", overflowY: "auto", padding: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <strong style={{ fontSize: 16, flex: 1 }}>🚀 Publicar ahora</strong>
          <button onClick={onCerrar} style={{ background: "none", border: "none", color: theme.text, fontSize: 18, cursor: "pointer" }}>✕</button>
        </div>

        <label style={etiqueta}>Cuenta y páginas</label>
        {cuentas.length === 0 ? (
          <div style={{ fontSize: 13, color: theme.subtext }}>Aún no tienes cuentas conectadas. Ve a la pestaña Cuentas.</div>
        ) : (
          <>
            <select value={cuentaId ?? ""} onChange={(e) => setCuentaId(Number(e.target.value))} style={campo}>
              {cuentas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              {paginas.map((p) => (
                <button key={p.id} style={chip(sel.has(p.id))} onClick={() => setSel((s) => { const n = new Set(s); n.has(p.id) ? n.delete(p.id) : n.add(p.id); return n; })}>{p.name}</button>
              ))}
              {paginas.length > 1 && <button style={chip(false)} onClick={() => setSel(new Set(paginas.map((p) => p.id)))}>Todas</button>}
            </div>
          </>
        )}

        <label style={etiqueta}>Tipo</label>
        <div style={{ display: "flex", gap: 6 }}>
          <button style={chip(tipo === "reel")} onClick={() => setTipo("reel")}>🎞️ Reel</button>
          <button style={chip(tipo === "video")} onClick={() => setTipo("video")}>🎬 Video</button>
        </div>

        <label style={etiqueta}>Título <span style={{ color: theme.subtext, fontWeight: 400 }}>(toca una sugerencia o escribe el tuyo)</span></label>
        <input value={titulo} maxLength={120} onChange={(e) => setTitulo(e.target.value)} style={campo} />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
          {titulos.map((t) => <button key={t} style={chip(t === titulo)} onClick={() => setTitulo(t)}>{t.length > 46 ? t.slice(0, 45) + "…" : t}</button>)}
        </div>

        <label style={etiqueta}>Descripción</label>
        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={3} style={campo} />

        <label style={etiqueta}>Hashtags <span style={{ color: theme.subtext, fontWeight: 400 }}>(en Facebook rinden mejor 3–5; ya van 5 marcados)</span></label>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {tags.todos.map((h) => <button key={h} style={chip(elegidos.has(h))} onClick={() => alternar(h)}>{h}</button>)}
        </div>

        {tendencias && tendencias.some((t) => t.hashtag) && (
          <>
            <label style={etiqueta}>🔥 Tendencias de hoy {geo && `(${geo})`} <span style={{ color: theme.subtext, fontWeight: 400 }}>(⭐ = tiene que ver con tu video; usa solo las que encajen)</span></label>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {tendencias.filter((t) => t.hashtag).slice(0, 10).map((t) => (
                <button key={t.termino} style={chip(elegidos.has(t.hashtag!))} title={t.trafico ? `${t.trafico} búsquedas` : undefined} onClick={() => alternar(t.hashtag!)}>
                  {t.relacionada ? "⭐ " : ""}{t.hashtag}
                </button>
              ))}
            </div>
          </>
        )}

        <div style={{ fontSize: 12, color: theme.subtext, margin: "14px 0 4px" }}>Así se verá el texto del post:</div>
        <div style={{ whiteSpace: "pre-wrap", fontSize: 13, border: `1px dashed ${theme.border}`, borderRadius: 6, padding: 8, minHeight: 36 }}>{mensaje || "(sin texto)"}</div>

        <div style={{ display: "flex", gap: 10, marginTop: 16, justifyContent: "flex-end" }}>
          <button onClick={onCerrar} style={{ background: "none", border: `1px solid ${theme.border}`, color: theme.text, borderRadius: 8, padding: "10px 16px", cursor: "pointer" }}>Cancelar</button>
          <button onClick={publicar} disabled={enviando || !sel.size} style={{ background: theme.accent, color: theme.accentText || "#fff", border: "none", borderRadius: 8, padding: "10px 18px", fontWeight: 600, cursor: "pointer", opacity: enviando || !sel.size ? 0.6 : 1 }}>
            {enviando ? "Publicando…" : `🚀 Publicar en ${sel.size || "…"} página${sel.size === 1 ? "" : "s"}`}
          </button>
        </div>
      </div>
    </div>
  );
}

