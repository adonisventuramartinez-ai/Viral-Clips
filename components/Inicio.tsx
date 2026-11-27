"use client";

import { useEffect, useState } from "react";
import { ICONO_TIPO, tiempoRelativo } from "@/lib/estados";
import type { Seccion } from "./FBSidebar";

interface Theme { cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string }

interface Estado {
  pendientes: number; atrasadas: number; completadas24h: number; conError: number;
  proximas: { id: number; tipo: string; titulo: string | null; archivo_nombre: string | null; fecha_programada: string; paginas: string[] }[];
  cron: { estado: "ok" | "lento" | "caido" | "sin_datos"; ultimo: string | null; segundos: number | null };
}

const CRON_INFO: Record<string, { color: string; titulo: string; ayuda: string }> = {
  ok: { color: "#22c55e", titulo: "El cron está funcionando", ayuda: "Las publicaciones saldrán a su hora." },
  lento: { color: "#f59e0b", titulo: "El cron tardó en responder", ayuda: "Revisa en cron-job.org que el job siga activo y corra cada minuto." },
  caido: { color: "#ef4444", titulo: "El cron está detenido", ayuda: "Nada se publicará hasta que lo arregles. En cron-job.org revisa que el job esté activo y que el header Authorization: Bearer <CRON_SECRET> sea correcto." },
  sin_datos: { color: "#6b7280", titulo: "Aún no hay datos del cron", ayuda: "Ejecuta la migración 003 en Supabase y espera un minuto. Si sigue igual, el cron no está llamando a /api/cron." },
};

export default function Inicio({ theme, onIr }: { theme: Theme; onIr: (s: Seccion) => void }) {
  const [e, setE] = useState<Estado | null>(null);
  const [fallo, setFallo] = useState(false);

  useEffect(() => {
    let vivo = true;
    const cargar = () =>
      fetch("/api/fb/estado").then((r) => r.json()).then((d) => { if (vivo) { d.error ? setFallo(true) : setE(d); } }).catch(() => vivo && setFallo(true));
    cargar();
    const t = setInterval(cargar, 30_000);
    return () => { vivo = false; clearInterval(t); };
  }, []);

  if (fallo) return <p style={{ color: theme.subtext }}>No se pudo cargar el resumen. Recarga la página.</p>;
  if (!e) return <p style={{ color: theme.subtext }}>Cargando…</p>;

  const info = CRON_INFO[e.cron.estado];
  const tarjetas = [
    { n: e.pendientes, t: "En cola", c: theme.accent, ir: "cola" as Seccion },
    { n: e.atrasadas, t: "Atrasadas", c: e.atrasadas ? "#f59e0b" : theme.subtext, ir: "cola" as Seccion },
    { n: e.completadas24h, t: "Publicadas (24 h)", c: "#22c55e", ir: "calendario" as Seccion },
    { n: e.conError, t: "Con error", c: e.conError ? "#ef4444" : theme.subtext, ir: "cola" as Seccion },
  ];
  const caja = { background: theme.formBg, border: `1px solid ${theme.border}`, borderRadius: 10, padding: 16 } as const;

  return (
    <div style={{ color: theme.text }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 16 }}>
        {tarjetas.map((t) => (
          <div key={t.t} onClick={() => onIr(t.ir)} style={{ ...caja, cursor: "pointer" }}>
            <div style={{ fontSize: 30, fontWeight: 700, color: t.c }}>{t.n}</div>
            <div style={{ fontSize: 13, color: theme.subtext }}>{t.t}</div>
          </div>
        ))}
      </div>

      <div style={{ ...caja, borderLeft: `4px solid ${info.color}`, marginBottom: 16 }}>
        <div style={{ fontWeight: 600 }}>{info.titulo}</div>
        <div style={{ fontSize: 13, color: theme.subtext, marginTop: 4 }}>
          {e.cron.ultimo ? `Última ejecución ${tiempoRelativo(e.cron.ultimo)}. ` : ""}{info.ayuda}
        </div>
      </div>

      <div style={caja}>
        <div style={{ fontWeight: 600, marginBottom: 10 }}>Próximas publicaciones</div>
        {e.proximas.length === 0 && (
          <div style={{ fontSize: 13, color: theme.subtext }}>
            No hay nada en cola. <a style={{ color: theme.accent, cursor: "pointer" }} onClick={() => onIr("lote")}>Programa un lote →</a>
          </div>
        )}
        {e.proximas.map((p) => (
          <div key={p.id} style={{ display: "flex", gap: 10, padding: "8px 0", borderTop: `1px solid ${theme.border}`, fontSize: 13, alignItems: "center" }}>
            <span>{ICONO_TIPO[p.tipo] || "📄"}</span>
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {p.titulo || p.archivo_nombre || "Sin título"}
              <span style={{ color: theme.subtext }}> · {p.paginas.join(", ")}</span>
            </span>
            <span style={{ color: theme.accent, whiteSpace: "nowrap" }}>{tiempoRelativo(p.fecha_programada)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

