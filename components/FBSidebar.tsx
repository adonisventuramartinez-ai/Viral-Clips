"use client";

import { useEffect, useState } from "react";

interface Theme {
  cardBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string;
}

export type Seccion =
  | "inicio" | "publicar" | "tiktok" | "programadas" | "lote" | "calendario" | "cola"
  | "historial" | "metricas" | "dashboard" | "eliminar" | "cuentas";

const ITEMS: { id: Seccion; icono: string; texto: string }[] = [
  { id: "inicio", icono: "🏠", texto: "Inicio" },
  { id: "publicar", icono: "✏️", texto: "Publicar ahora" },
  { id: "tiktok", icono: "🎵", texto: "TikTok / Instagram" },
  { id: "programadas", icono: "🗓️", texto: "Programar" },
  { id: "lote", icono: "📦", texto: "Lote" },
  { id: "calendario", icono: "📅", texto: "Calendario" },
  { id: "cola", icono: "📋", texto: "Cola" },
  { id: "historial", icono: "📜", texto: "Historial" },
  { id: "metricas", icono: "🚀", texto: "Métricas / Vistas" },
  { id: "dashboard", icono: "📊", texto: "Estadísticas" },
  { id: "eliminar", icono: "🗑️", texto: "Eliminador" },
  { id: "cuentas", icono: "👥", texto: "Cuentas" },
];

const CSS = `
.sb{width:210px;flex-shrink:0;position:sticky;top:0;align-self:flex-start;padding:16px 8px;display:flex;flex-direction:column;gap:4px;box-sizing:border-box}
.sb button{width:100%;text-align:left}
@media (max-width:820px){
  .app-wrap{flex-direction:column !important}
  .sb{width:100%;position:static;flex-direction:row;overflow-x:auto;padding:8px}
  .sb button{width:auto;white-space:nowrap}
  .sb .sb-fin{display:none}
}`;

const COLOR_CRON: Record<string, string> = { ok: "#22c55e", lento: "#f59e0b", caido: "#ef4444", sin_datos: "#6b7280" };
const TEXTO_CRON: Record<string, string> = {
  ok: "Cron activo", lento: "Cron lento", caido: "Cron detenido", sin_datos: "Cron sin datos",
};

export default function Sidebar({
  theme, activo, onSelect, onCerrarSesion,
}: { theme: Theme; activo: Seccion; onSelect: (s: Seccion) => void; onCerrarSesion: () => void }) {
  const [cron, setCron] = useState<string>("sin_datos");
  const [pendientes, setPendientes] = useState(0);
  const [errores, setErrores] = useState(0);

  useEffect(() => {
    let vivo = true;
    const cargar = () =>
      fetch("/api/fb/estado")
        .then((r) => r.json())
        .then((d) => {
          if (!vivo || d.error) return;
          setCron(d.cron?.estado || "sin_datos");
          setPendientes(d.pendientes || 0);
          setErrores(d.conError || 0);
        })
        .catch(() => {});
    cargar();
    const t = setInterval(cargar, 30_000);
    return () => { vivo = false; clearInterval(t); };
  }, []);

  const insignia = (id: Seccion) => (id === "cola" ? pendientes : 0);

  return (
    <aside className="sb" style={{ borderRight: `1px solid ${theme.border}`, background: theme.cardBg }}>
      <style>{CSS}</style>
      {ITEMS.map((it) => {
        const on = activo === it.id;
        const n = insignia(it.id);
        return (
          <button
            key={it.id}
            onClick={() => onSelect(it.id)}
            style={{
              padding: "10px 12px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 14,
              background: on ? theme.accentBg : "transparent",
              color: on ? theme.accent : theme.subtext,
              fontWeight: on ? 600 : 400,
              display: "flex", justifyContent: "space-between", gap: 8,
            }}
          >
            <span>{it.icono} {it.texto}</span>
            {n > 0 && <span style={{ fontSize: 11, background: theme.accent, color: (theme as any).accentText || "#fff", borderRadius: 10, padding: "1px 7px" }}>{n}</span>}
          </button>
        );
      })}

      <div className="sb-fin" style={{ marginTop: 16, paddingTop: 12, borderTop: `1px solid ${theme.border}`, fontSize: 12, color: theme.subtext }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: COLOR_CRON[cron] }} />
          {TEXTO_CRON[cron]}
        </div>
        {errores > 0 && (
          <div style={{ color: "#ef4444", cursor: "pointer", marginBottom: 6 }} onClick={() => onSelect("cola")}>
            ⚠️ {errores} con error
          </div>
        )}
        <button onClick={onCerrarSesion} style={{ background: "none", border: "none", color: theme.subtext, cursor: "pointer", padding: 0, fontSize: 12 }}>
          🔒 Cerrar sesión
        </button>
      </div>
    </aside>
  );
}

