"use client";

import { useEffect, useMemo, useState } from "react";
import { COLOR_ESTADO, ETIQUETA_ESTADO, ICONO_TIPO } from "@/lib/estados";

interface Theme { cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string }
interface Post {
  id: number; paginas: { id: string; name: string }[]; tipo: string; titulo: string | null;
  archivo_nombre: string | null; fecha_programada: string; estado: string;
}

const clave = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
const hora = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export default function Calendario({ theme }: { theme: Theme }) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [mes, setMes] = useState<Date>(() => { const d = new Date(); d.setDate(1); d.setHours(0, 0, 0, 0); return d; });
  const [dia, setDia] = useState<string | null>(clave(new Date()));

  useEffect(() => {
    fetch("/api/fb/schedule").then((r) => r.json()).then((d) => setPosts(d.posts || [])).catch(() => {});
  }, []);

  const porDia = useMemo(() => {
    const m: Record<string, Post[]> = {};
    for (const p of posts) {
      if (p.estado === "cancelado") continue;
      const k = clave(new Date(p.fecha_programada));
      if (!m[k]) m[k] = [];
      m[k].push(p);
    }
    for (const k of Object.keys(m)) m[k].sort((a, b) => a.fecha_programada.localeCompare(b.fecha_programada));
    return m;
  }, [posts]);

  const celdas = useMemo(() => {
    const ini = new Date(mes);
    ini.setDate(1 - ((mes.getDay() + 6) % 7)); // semana empieza en lunes
    return Array.from({ length: 42 }, (_, i) => { const d = new Date(ini); d.setDate(ini.getDate() + i); return d; });
  }, [mes]);

  const cambiar = (n: number) => setMes((m) => { const d = new Date(m); d.setMonth(d.getMonth() + n); return d; });
  const hoy = clave(new Date());
  const delDia = dia ? porDia[dia] || [] : [];
  const btn = { background: "none", border: `1px solid ${theme.border}`, color: theme.text, borderRadius: 6, padding: "6px 12px", cursor: "pointer" } as const;

  return (
    <div style={{ color: theme.text }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <button style={btn} onClick={() => cambiar(-1)}>‹</button>
        <button style={btn} onClick={() => cambiar(1)}>›</button>
        <button style={btn} onClick={() => { const d = new Date(); d.setDate(1); d.setHours(0, 0, 0, 0); setMes(d); setDia(clave(new Date())); }}>Hoy</button>
        <strong style={{ fontSize: 16, textTransform: "capitalize" }}>{mes.toLocaleDateString([], { month: "long", year: "numeric" })}</strong>
      </div>

      <div style={{ overflowX: "auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(84px, 1fr))", gap: 4, minWidth: 600 }}>
          {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((n) => (
            <div key={n} style={{ fontSize: 12, color: theme.subtext, textAlign: "center", padding: 4 }}>{n}</div>
          ))}
          {celdas.map((d) => {
            const k = clave(d);
            const lista = porDia[k] || [];
            const fuera = d.getMonth() !== mes.getMonth();
            return (
              <div
                key={k}
                onClick={() => setDia(k)}
                style={{
                  minHeight: 78, padding: 4, borderRadius: 6, cursor: "pointer", boxSizing: "border-box",
                  background: dia === k ? theme.accentBg : theme.formBg,
                  border: `1px solid ${k === hoy ? theme.accent : theme.border}`,
                  opacity: fuera ? 0.45 : 1,
                }}
              >
                <div style={{ fontSize: 12, color: k === hoy ? theme.accent : theme.subtext, fontWeight: k === hoy ? 700 : 400 }}>{d.getDate()}</div>
                {lista.slice(0, 3).map((p) => (
                  <div key={p.id} style={{ fontSize: 10, marginTop: 2, color: COLOR_ESTADO[p.estado], whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    ● {hora(p.fecha_programada)}
                  </div>
                ))}
                {lista.length > 3 && <div style={{ fontSize: 10, color: theme.subtext }}>+{lista.length - 3} más</div>}
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ marginTop: 16, background: theme.formBg, border: `1px solid ${theme.border}`, borderRadius: 10, padding: 14 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>
          {dia ? `${delDia.length} publicación${delDia.length === 1 ? "" : "es"} este día` : "Elige un día"}
        </div>
        {delDia.map((p) => (
          <div key={p.id} style={{ display: "flex", gap: 10, fontSize: 13, padding: "6px 0", borderTop: `1px solid ${theme.border}`, alignItems: "center" }}>
            <span style={{ color: theme.accent, width: 56 }}>{hora(p.fecha_programada)}</span>
            <span>{ICONO_TIPO[p.tipo] || "📄"}</span>
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {p.titulo || p.archivo_nombre || "Sin título"} <span style={{ color: theme.subtext }}>· {p.paginas.map((x) => x.name).join(", ")}</span>
            </span>
            <span style={{ color: COLOR_ESTADO[p.estado], fontSize: 12 }}>{ETIQUETA_ESTADO[p.estado]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

