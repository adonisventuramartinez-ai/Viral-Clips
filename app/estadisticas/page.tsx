"use client";
import { useEffect, useState } from "react";

type S = { total: number; avg: number; best: number; mb: number; days: Record<string, number> };

export default function Estadisticas() {
  const [s, setS] = useState<S | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let who = "";
    try { who = localStorage.getItem("cf_clipper") || ""; } catch {}
    fetch(`/api/hub/mystats${who ? `?clipper=${encodeURIComponent(who)}` : ""}`).then((r) => r.json()).then((j) => (j.error ? setErr(j.error) : setS(j))).catch(() => setErr("No se pudo conectar"));
  }, []);
  const max = s ? Math.max(1, ...Object.values(s.days)) : 1;
  const k = (label: string, v: string | number) => <div className="card"><small style={{ color: "var(--muted)" }}>{label}</small><div style={{ fontSize: 32, fontWeight: 700 }}>{v}</div></div>;
  return (
    <>
      <h1>📊 Estadísticas</h1>
      <p className="sub">Tus números (según el nombre que usas en Proyecto).</p>
      {err && <div className="banner">{err}</div>}
      {s && (
        <>
          <div className="grid3" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>{k("Clips creados", s.total)}{k("Score promedio", s.avg + "%")}{k("Mejor clip", s.best + "%")}{k("Espacio usado", s.mb + " MB")}</div>
          <div className="card" style={{ marginTop: 16 }}>
            <b>Clips por día (últimos 7)</b>
            <div className="bars">{Object.entries(s.days).map(([d, n]) => (
              <div key={d}>{n}<i style={{ height: `${(n / max) * 100}%` }} />{d.slice(5)}</div>
            ))}</div>
          </div>
        </>
      )}
    </>
  );
}
