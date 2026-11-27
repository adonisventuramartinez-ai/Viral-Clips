"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Theme { cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string }

interface Fila {
  id: string; paginaId: string; pagina: string; tipo: string; titulo: string | null; fecha: string | null;
  vistas: number | null; alcance: number | null; reacciones: number | null; comentarios: number | null;
  compartidos: number | null; permalink: string | null; error: string | null;
}
interface PaginaInfo { id: string; nombre: string; seguidores: number | null; vistas28: number | null; error: string | null }
interface Datos {
  items: Fila[]; paginas: PaginaInfo[]; avisos: string[]; actualizado: string;
  totales: { vistas: number; alcance: number; reacciones: number; comentarios: number };
}

const fmt = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n.toLocaleString("es"));
const ICONO: Record<string, string> = { foto: "🖼️", video: "🎬", reel: "🎞️" };

const CHECKLIST = [
  "App de Facebook en modo LIVE (en Desarrollo solo te ven los que tienen rol en la app).",
  "Reconecta tus cuentas después de actualizar: se pidió el permiso nuevo read_insights.",
  "Reels: siempre con la API oficial (ya corregido). Vertical 9:16, 5-90 s, con gancho en el primer segundo.",
  "No publiques el mismo video en todas las páginas a la vez (el panel ahora las escalona solas).",
  "Contenido propio o con edición real: los reposts de TikTok/Instagram sin marca son los que más castiga Facebook.",
  "Publica a diario y a horas distintas; mira abajo qué posts rinden más y repite ese formato.",
];

export default function Metricas({ theme }: { theme: Theme }) {
  const [d, setD] = useState<Datos | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [orden, setOrden] = useState<"fecha" | "vistas">("vistas");

  const cargar = useCallback(async (refrescar: boolean) => {
    setCargando(true);
    setError(null);
    try {
      const r = await fetch(`/api/fb/insights${refrescar ? "?refrescar=1" : ""}`);
      const j = await r.json();
      if (j.error) throw new Error(j.error);
      setD(j);
    } catch (e: any) {
      setError(e.message || "No se pudieron cargar las métricas");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargar(false); }, [cargar]);

  const filas = useMemo(() => {
    const l = [...(d?.items || [])];
    l.sort((a, b) =>
      orden === "vistas"
        ? (b.vistas ?? -1) - (a.vistas ?? -1)
        : new Date(b.fecha || 0).getTime() - new Date(a.fecha || 0).getTime()
    );
    return l;
  }, [d, orden]);

  const grafica = useMemo(
    () => [...(d?.items || [])].filter((f) => f.vistas !== null).sort((a, b) => (b.vistas as number) - (a.vistas as number)).slice(0, 8)
      .map((f) => ({ nombre: `${f.pagina.slice(0, 14)} · ${(f.titulo || f.tipo).slice(0, 12)}`, vistas: f.vistas as number })),
    [d]
  );

  const caja = { background: theme.formBg, border: `1px solid ${theme.border}`, borderRadius: 10, padding: 16 } as const;
  const th = { textAlign: "left" as const, fontSize: 12, color: theme.subtext, fontWeight: 500, padding: "6px 8px", borderBottom: `1px solid ${theme.border}` };
  const td = { fontSize: 13, padding: "8px", borderBottom: `1px solid ${theme.border}`, color: theme.text };

  return (
    <div style={{ color: theme.text }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <button onClick={() => cargar(true)} disabled={cargando}
          style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: theme.accent, color: "white", fontWeight: 600, cursor: cargando ? "wait" : "pointer", opacity: cargando ? 0.7 : 1 }}>
          {cargando ? "Leyendo Facebook…" : "🔄 Actualizar ahora"}
        </button>
        {d && <span style={{ fontSize: 12, color: theme.subtext }}>Actualizado {new Date(d.actualizado).toLocaleTimeString("es")}</span>}
      </div>

      {error && <div style={{ ...caja, borderLeft: "4px solid #ef4444", marginBottom: 16 }}>{error}</div>}

      {d?.avisos.map((a, i) => (
        <div key={i} style={{ ...caja, borderLeft: "4px solid #f59e0b", marginBottom: 12, fontSize: 14 }}>⚠️ {a}</div>
      ))}

      {d && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 16 }}>
          {[
            { t: "Vistas", n: d.totales.vistas, c: theme.accent },
            { t: "Alcance", n: d.totales.alcance, c: "#7c3aed" },
            { t: "Reacciones", n: d.totales.reacciones, c: "#22c55e" },
            { t: "Comentarios", n: d.totales.comentarios, c: "#f59e0b" },
          ].map((x) => (
            <div key={x.t} style={caja}>
              <div style={{ fontSize: 30, fontWeight: 700, color: x.c }}>{fmt(x.n)}</div>
              <div style={{ fontSize: 13, color: theme.subtext }}>{x.t}</div>
            </div>
          ))}
        </div>
      )}

      {grafica.length > 0 && (
        <div style={{ ...caja, marginBottom: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>🔥 Tus publicaciones con más vistas</div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={grafica} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
              <XAxis type="number" tick={{ fontSize: 12, fill: theme.subtext }} allowDecimals={false} />
              <YAxis type="category" dataKey="nombre" width={150} tick={{ fontSize: 11, fill: theme.subtext }} />
              <Tooltip contentStyle={{ background: theme.cardBg, border: `1px solid ${theme.border}`, fontSize: 12 }} />
              <Bar dataKey="vistas" fill={theme.accent} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {d && d.paginas.length > 0 && (
        <div style={{ ...caja, marginBottom: 16, overflowX: "auto" }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>📄 Páginas</div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr><th style={th}>Página</th><th style={th}>Seguidores</th><th style={th}>Vistas (28 días)</th></tr></thead>
            <tbody>
              {d.paginas.map((p) => (
                <tr key={p.id}>
                  <td style={td}>{p.nombre}</td>
                  <td style={td}>{fmt(p.seguidores)}</td>
                  <td style={td} title={p.error || ""}>{fmt(p.vistas28)}{p.error && p.vistas28 === null ? " ⚠️" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {d && (
        <div style={{ ...caja, marginBottom: 16, overflowX: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
            <div style={{ fontWeight: 600 }}>📋 Publicaciones ({filas.length})</div>
            <div style={{ display: "flex", gap: 6 }}>
              {(["vistas", "fecha"] as const).map((o) => (
                <button key={o} onClick={() => setOrden(o)}
                  style={{ padding: "4px 12px", borderRadius: 14, fontSize: 12, cursor: "pointer", border: `1px solid ${orden === o ? theme.accent : theme.border}`, background: orden === o ? theme.accent : "transparent", color: orden === o ? "white" : theme.text }}>
                  {o === "vistas" ? "Más vistas" : "Más recientes"}
                </button>
              ))}
            </div>
          </div>
          {filas.length === 0 ? (
            <p style={{ color: theme.subtext, fontSize: 14 }}>Sin datos todavía.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr><th style={th}>Publicación</th><th style={th}>Página</th><th style={th}>Vistas</th><th style={th}>Alcance</th><th style={th}>❤️</th><th style={th}>💬</th><th style={th}></th></tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={f.id + f.paginaId}>
                    <td style={td}>{ICONO[f.tipo] || "📄"} {f.titulo || "Sin título"}
                      <div style={{ fontSize: 11, color: theme.subtext }}>{f.fecha ? new Date(f.fecha).toLocaleString("es") : ""}</div></td>
                    <td style={td}>{f.pagina}</td>
                    <td style={{ ...td, fontWeight: 600 }} title={f.error || ""}>{fmt(f.vistas)}{f.error && f.vistas === null ? " ⚠️" : ""}</td>
                    <td style={td}>{fmt(f.alcance)}</td>
                    <td style={td}>{fmt(f.reacciones)}</td>
                    <td style={td}>{fmt(f.comentarios)}</td>
                    <td style={td}>{f.permalink && <a href={f.permalink} target="_blank" rel="noreferrer" style={{ color: theme.accent }}>Abrir ↗</a>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div style={caja}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>🚀 Checklist para que las vistas despeguen</div>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, lineHeight: 1.7, color: theme.text }}>
          {CHECKLIST.map((c) => <li key={c}>{c}</li>)}
        </ul>
      </div>
    </div>
  );
}

