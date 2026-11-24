"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import type { Seccion } from "./FBSidebar";
import PublicarYa, { VideoListo } from "./PublicarYa";

interface Theme { cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string; accentText?: string }

interface Importacion {
  id: number; tipo: "video" | "perfil"; url: string; estado: string; titulo: string | null; autor: string | null;
  duracion: number | null; bytes: number | null; miniatura: string | null; error: string | null;
  descripcion?: string | null; archivo_url?: string | null;
  videos: { url: string; titulo: string; duracion: number | null }[] | null;
}

const COLOR: Record<string, string> = { pendiente: "#f59e0b", procesando: "#38bdf8", listo: "#22c55e", error: "#ef4444", usado: "#6b7280" };
const TEXTO: Record<string, string> = { pendiente: "En cola…", procesando: "Descargando…", listo: "Listo", error: "Error", usado: "Programado" };
const mb = (b: number | null) => (b ? `${(b / 1048576).toFixed(1)} MB` : "");
const seg = (s: number | null) => (s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : "");

export default function TikTok({ theme, onIr }: { theme: Theme; onIr: (s: Seccion) => void }) {
  const [items, setItems] = useState<Importacion[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [abierto, setAbierto] = useState<number | null>(null);
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [publicando, setPublicando] = useState<VideoListo | null>(null);

  async function cargar() {
    try {
      const d = await (await fetch("/api/fb/importar")).json();
      if (!d.error) setItems(d.importaciones || []);
    } catch {}
  }
  const hayActivos = items.some((i) => i.estado === "pendiente" || i.estado === "procesando");
  useEffect(() => {
    cargar();
    const t = setInterval(cargar, hayActivos ? 5000 : 20000);
    return () => clearInterval(t);
  }, [hayActivos]);

  async function importar(urls: string[]) {
    setEnviando(true);
    try {
      const res = await (await fetch("/api/fb/importar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      })).json();
      if (res.error) throw new Error(res.error);
      if (res.creados) toast.success(`${res.creados} en cola. Tarda 1–2 minutos en empezar.`);
      if (res.omitidos?.length) toast(`${res.omitidos.length} ya estaban importados o en cola`);
      if (res.invalidos?.length) toast.error(`${res.invalidos.length} enlace(s) no válidos: ${res.invalidos.join(", ")}`, { duration: 7000 });
      if (res.despacho && !res.despacho.ok) toast.error(`No se pudo despertar el worker: ${res.despacho.error}`, { duration: 9000 });
      setTexto("");
      setMarcados(new Set());
      cargar();
    } catch (e: any) {
      toast.error(e.message || "Error al importar");
    } finally {
      setEnviando(false);
    }
  }

  async function accion(id: number, tipo: "borrar" | "reintentar") {
    if (tipo === "borrar" && !confirm("¿Quitar de la lista? Si el video aún no se usó, también se borra el archivo.")) return;
    const r = await fetch(`/api/importar/${id}`, tipo === "borrar"
      ? { method: "DELETE" }
      : { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accion: "reintentar" }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) toast.error(d.error || "No se pudo");
    cargar();
  }

  async function procesarAhora() {
    try {
      const d = await (await fetch("/api/fb/importar", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accion: "procesar" }),
      })).json();
      if (d.despacho?.ok) toast.success("Worker despertado");
      else toast.error(d.despacho?.error || d.error || "No se pudo despertar el worker", { duration: 9000 });
    } catch (e: any) {
      toast.error(e?.message || "No se pudo despertar el worker");
    }
  }

  const yaImportadas = new Set(items.filter((i) => i.tipo === "video" && i.estado !== "error").map((i) => i.url));
  const videos = items.filter((i) => i.tipo === "video");
  const listos = videos.filter((i) => i.estado === "listo");
  const enProceso = videos.filter((i) => i.estado !== "listo" && i.estado !== "usado");
  const perfiles = items.filter((i) => i.tipo === "perfil");
  const hayAtascados = items.some((i) => i.estado === "pendiente");

  const caja = { background: theme.formBg, border: `1px solid ${theme.border}`, borderRadius: 10, padding: 16, marginBottom: 16 } as const;
  const boton = { background: "none", border: `1px solid ${theme.border}`, color: theme.text, borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: 12 } as const;
  const principal = { background: theme.accent, color: theme.accentText || "#fff", border: "none", borderRadius: 8, padding: "10px 18px", fontWeight: 600, cursor: "pointer" } as const;

  return (
    <div style={{ color: theme.text }}>
      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 12px" }}>🎵 Importar de TikTok e Instagram</h3>

      <div style={caja}>
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder={"Pega enlaces de videos de TikTok o Instagram (uno por línea) o un perfil de TikTok (@usuario)\nhttps://www.tiktok.com/@usuario/video/123…\nhttps://vm.tiktok.com/ZM…\nhttps://www.instagram.com/reel/C8…\n@usuario"}
          style={{ width: "100%", minHeight: 100, padding: 10, borderRadius: 6, border: `1px solid ${theme.border}`, background: theme.cardBg, color: theme.text, boxSizing: "border-box" }}
        />
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 10, flexWrap: "wrap" }}>
          <button style={{ ...principal, opacity: enviando ? 0.6 : 1 }} disabled={enviando || !texto.trim()} onClick={() => importar(texto.split(/\s+/).filter(Boolean))}>
            {enviando ? "Enviando…" : "Importar"}
          </button>
          <span style={{ fontSize: 12, color: theme.subtext }}>
            ⚠️ Se descargan sin marca de agua. Úsalo con contenido tuyo o con permiso de su autor: republicar videos ajenos puede violar derechos de autor y las reglas de TikTok, Instagram y Facebook.
          </span>
        </div>
      </div>

      {hayAtascados && (
        <div style={{ fontSize: 12, color: theme.subtext, marginBottom: 12 }}>
          ¿Lleva más de 3 minutos en cola? <a style={{ color: theme.accent, cursor: "pointer" }} onClick={procesarAhora}>Despertar el worker</a>
        </div>
      )}

      {perfiles.map((p) => (
        <div key={p.id} style={caja}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <strong>👤 {p.url.split("/").pop()}</strong>
            <span style={{ color: COLOR[p.estado], fontSize: 12 }}>{p.estado === "listo" ? `${p.videos?.length || 0} videos encontrados` : TEXTO[p.estado]}</span>
            <span style={{ flex: 1 }} />
            {p.estado === "listo" && <button style={boton} onClick={() => { setAbierto(abierto === p.id ? null : p.id); setMarcados(new Set()); }}>{abierto === p.id ? "Cerrar" : "Elegir videos"}</button>}
            {p.estado === "error" && <button style={boton} onClick={() => accion(p.id, "reintentar")}>↻ Reintentar</button>}
            <button style={boton} onClick={() => accion(p.id, "borrar")}>✕</button>
          </div>
          {p.error && <div style={{ color: "#ef4444", fontSize: 12, marginTop: 6 }}>{p.error}</div>}
          {abierto === p.id && p.videos && (
            <div style={{ marginTop: 10 }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <button style={boton} onClick={() => setMarcados(new Set(p.videos!.map((v) => v.url).filter((u) => !yaImportadas.has(u))))}>Marcar todos</button>
                <button style={boton} onClick={() => setMarcados(new Set())}>Ninguno</button>
              </div>
              {p.videos.map((v) => {
                const ya = yaImportadas.has(v.url);
                return (
                  <label key={v.url} style={{ display: "flex", gap: 8, fontSize: 13, padding: "5px 0", borderTop: `1px solid ${theme.border}`, opacity: ya ? 0.5 : 1 }}>
                    <input type="checkbox" disabled={ya} checked={marcados.has(v.url)} onChange={() => {
                      const n = new Set(marcados); n.has(v.url) ? n.delete(v.url) : n.add(v.url); setMarcados(n);
                    }} />
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v.titulo || v.url}</span>
                    <span style={{ color: theme.subtext }}>{ya ? "ya importado" : seg(v.duracion)}</span>
                  </label>
                );
              })}
              <button style={{ ...principal, marginTop: 10, opacity: marcados.size ? 1 : 0.5 }} disabled={!marcados.size || enviando} onClick={() => importar([...marcados])}>
                Descargar {marcados.size} seleccionado{marcados.size === 1 ? "" : "s"}
              </button>
            </div>
          )}
        </div>
      ))}

      {enProceso.length > 0 && (
        <div style={caja}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>En proceso ({enProceso.length})</div>
          {enProceso.map((i) => (
            <div key={i.id} style={{ padding: "6px 0", borderTop: `1px solid ${theme.border}`, fontSize: 13 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ color: COLOR[i.estado], width: 100 }}>{TEXTO[i.estado]}</span>
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: theme.subtext }}>{i.url}</span>
                {i.estado === "error" && <button style={boton} onClick={() => accion(i.id, "reintentar")}>↻</button>}
                {i.estado !== "procesando" && <button style={boton} onClick={() => accion(i.id, "borrar")}>✕</button>}
              </div>
              {i.error && <div style={{ color: "#ef4444", fontSize: 12, marginTop: 4 }}>{i.error}</div>}
            </div>
          ))}
        </div>
      )}

      <div style={caja}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 600 }}>Listos para programar ({listos.length})</span>
          <span style={{ flex: 1 }} />
          {listos.length > 0 && <button style={principal} onClick={() => onIr("lote")}>📦 Programar en lote →</button>}
        </div>
        {listos.length === 0 && <div style={{ fontSize: 13, color: theme.subtext }}>Los videos descargados (TikTok o Instagram) aparecerán aquí.</div>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
          {listos.map((i) => (
            <div key={i.id} style={{ border: `1px solid ${theme.border}`, borderRadius: 8, overflow: "hidden", background: theme.cardBg }}>
              <div style={{ height: 150, background: "#000", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {i.miniatura ? <img src={i.miniatura} alt="" style={{ maxWidth: "100%", maxHeight: "100%" }} /> : <span style={{ fontSize: 30 }}>🎬</span>}
              </div>
              <div style={{ padding: 8, fontSize: 12 }}>
                <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{i.titulo || "Sin descripción"}</div>
                <div style={{ color: theme.subtext }}>{[i.autor && `@${i.autor}`, seg(i.duracion), mb(i.bytes)].filter(Boolean).join(" · ")}</div>
                <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                  <button
                    style={{ ...principal, padding: "5px 10px", fontSize: 12, borderRadius: 6 }}
                    disabled={!i.archivo_url}
                    onClick={() => i.archivo_url && setPublicando({ id: i.id, titulo: i.titulo, descripcion: i.descripcion ?? null, autor: i.autor, archivo_url: i.archivo_url, miniatura: i.miniatura })}
                  >🚀 Publicar ahora</button>
                  <button style={boton} onClick={() => accion(i.id, "borrar")}>Quitar</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      {publicando && <PublicarYa video={publicando} theme={theme} onCerrar={() => setPublicando(null)} onHecho={cargar} />}
    </div>
  );
}

