"use client";

import { useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";

interface Resultado {
  pagina: string;
  exito: boolean;
  mensaje: string;
}

interface PublicacionHistorial {
  id: string;
  fecha: string;
  tipo: string;
  titulo: string;
  mensaje: string;
  paginas: number;
  exitos: number;
  errores: number;
  resultados: Resultado[];
}

interface Theme {
  cardBg: string;
  border: string;
  text: string;
  subtext: string;
  accent: string;
}

interface DashboardProps {
  historial: PublicacionHistorial[];
  theme: Theme;
}

type Rango = 7 | 30 | 90 | 0; // 0 = todo

const COLORES_PIE = ["#34a853", "#c62828"];
const MEDALLAS = ["🥇", "🥈", "🥉"];

export default function Dashboard({ historial, theme }: DashboardProps) {
  const [rango, setRango] = useState<Rango>(30);

  const historialFiltrado = useMemo(() => {
    if (rango === 0) return historial;
    const limite = Date.now() - rango * 24 * 60 * 60 * 1000;
    return historial.filter((p) => {
      const t = new Date(p.fecha).getTime();
      return !isNaN(t) && t >= limite;
    });
  }, [historial, rango]);

  const stats = useMemo(() => {
    const totalPub = historialFiltrado.length;
    const exitos = historialFiltrado.reduce((acc, p) => acc + p.exitos, 0);
    const errores = historialFiltrado.reduce((acc, p) => acc + p.errores, 0);
    const tasa = exitos + errores > 0 ? (exitos / (exitos + errores)) * 100 : 0;
    return { totalPub, exitos, errores, tasa };
  }, [historialFiltrado]);

  const tendencia = useMemo(() => {
    const porDia: { [key: string]: number } = {};
    historialFiltrado.forEach((p) => {
      const t = new Date(p.fecha);
      if (isNaN(t.getTime())) return;
      const clave = t.toLocaleDateString("es", { day: "2-digit", month: "2-digit" });
      porDia[clave] = (porDia[clave] || 0) + 1;
    });
    return Object.entries(porDia)
      .map(([dia, publicaciones]) => ({ dia, publicaciones }))
      .slice(-30);
  }, [historialFiltrado]);

  const ranking = useMemo(() => {
    const paginas: { [key: string]: number } = {};
    historialFiltrado.forEach((p) => {
      p.resultados.forEach((r) => {
        if (r.exito) paginas[r.pagina] = (paginas[r.pagina] || 0) + 1;
      });
    });
    return Object.entries(paginas)
      .map(([nombre, publicaciones]) => ({ nombre, publicaciones }))
      .sort((a, b) => b.publicaciones - a.publicaciones)
      .slice(0, 5);
  }, [historialFiltrado]);

  const pieData = [
    { name: "Éxitos", value: stats.exitos },
    { name: "Errores", value: stats.errores },
  ];

  const filtros: { valor: Rango; label: string }[] = [
    { valor: 7, label: "7 días" },
    { valor: 30, label: "30 días" },
    { valor: 90, label: "90 días" },
    { valor: 0, label: "Todo" },
  ];

  if (historial.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "40px 20px", color: theme.subtext }}>
        <span style={{ fontSize: "48px", display: "block", marginBottom: "12px" }}>📊</span>
        <p>No hay datos para mostrar</p>
        <p style={{ fontSize: "13px" }}>Publica contenido para ver estadísticas aquí</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        {filtros.map((f) => (
          <button
            key={f.valor}
            onClick={() => setRango(f.valor)}
            style={{
              padding: "6px 14px",
              borderRadius: "16px",
              border: `1px solid ${rango === f.valor ? theme.accent : theme.border}`,
              background: rango === f.valor ? theme.accent : "transparent",
              color: rango === f.valor ? (theme as any).accentText || "white" : theme.text,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "12px",
          marginBottom: "24px",
        }}
      >
        <div style={{ background: theme.cardBg, padding: "16px", borderRadius: "8px", border: `1px solid ${theme.border}`, textAlign: "center" }}>
          <div style={{ fontSize: "13px", color: theme.subtext }}>Total Publicaciones</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: theme.accent }}>{stats.totalPub}</div>
        </div>
        <div style={{ background: theme.cardBg, padding: "16px", borderRadius: "8px", border: `1px solid ${theme.border}`, textAlign: "center" }}>
          <div style={{ fontSize: "13px", color: theme.subtext }}>Exitosas</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#34a853" }}>{stats.exitos}</div>
        </div>
        <div style={{ background: theme.cardBg, padding: "16px", borderRadius: "8px", border: `1px solid ${theme.border}`, textAlign: "center" }}>
          <div style={{ fontSize: "13px", color: theme.subtext }}>Tasa de Éxito</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#7c3aed" }}>{stats.tasa.toFixed(1)}%</div>
        </div>
        <div style={{ background: theme.cardBg, padding: "16px", borderRadius: "8px", border: `1px solid ${theme.border}`, textAlign: "center" }}>
          <div style={{ fontSize: "13px", color: theme.subtext }}>Fallidas</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#c62828" }}>{stats.errores}</div>
        </div>
      </div>

      {tendencia.length > 0 && (
        <div style={{ background: theme.cardBg, padding: "20px", borderRadius: "8px", border: `1px solid ${theme.border}`, marginBottom: "24px" }}>
          <h4 style={{ fontSize: "15px", fontWeight: 500, margin: "0 0 16px 0", color: theme.text }}>
            📈 Tendencia de publicaciones
          </h4>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={tendencia}>
              <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
              <XAxis dataKey="dia" tick={{ fontSize: 12, fill: theme.subtext }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: theme.subtext }} />
              <Tooltip contentStyle={{ background: theme.cardBg, border: `1px solid ${theme.border}`, fontSize: "12px" }} />
              <Line type="monotone" dataKey="publicaciones" stroke={theme.accent} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
        {(stats.exitos > 0 || stats.errores > 0) && (
          <div style={{ background: theme.cardBg, padding: "20px", borderRadius: "8px", border: `1px solid ${theme.border}` }}>
            <h4 style={{ fontSize: "15px", fontWeight: 500, margin: "0 0 16px 0", color: theme.text }}>
              🥧 Éxito vs Error
            </h4>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70} paddingAngle={4}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORES_PIE[i]} />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Tooltip contentStyle={{ fontSize: "12px" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {ranking.length > 0 && (
          <div style={{ background: theme.cardBg, padding: "20px", borderRadius: "8px", border: `1px solid ${theme.border}` }}>
            <h4 style={{ fontSize: "15px", fontWeight: 500, margin: "0 0 16px 0", color: theme.text }}>
              🏆 Ranking de páginas
            </h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {ranking.map((p, i) => (
                <div key={p.nombre} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "16px", width: "24px" }}>{MEDALLAS[i] || `${i + 1}.`}</span>
                  <span style={{ flex: 1, fontSize: "13px", color: theme.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {p.nombre}
                  </span>
                  <span style={{ fontSize: "13px", fontWeight: 600, color: theme.accent }}>{p.publicaciones}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

