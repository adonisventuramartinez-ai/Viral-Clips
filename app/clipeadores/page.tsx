"use client";
import { useHub } from "@/lib/useHub";

type Row = { clipper: string; clips: number; best_score: number; avg_score: number };

export default function Clipeadores() {
  const { items, error } = useHub<Row>("clippers");
  return (
    <>
      <h1>⭐ Clipeadores</h1>
      <p className="sub">Ranking de la comunidad: quién ha creado más clips (el nombre lo eliges en Proyecto).</p>
      {error && <div className="banner">{error}</div>}
      <div className="card">
        {items === null && !error && <small style={{ color: "var(--muted)" }}>Cargando…</small>}
        {items && !items.length && <small style={{ color: "var(--muted)" }}>Todavía no hay clipeadores. Escribe tu nombre en Proyecto y genera tu primer clip.</small>}
        {items && items.length > 0 && (
          <table className="table">
            <thead><tr><th>#</th><th>Clipeador</th><th>Clips</th><th>Mejor score</th><th>Promedio</th></tr></thead>
            <tbody>
              {items.map((r, i) => (
                <tr key={r.clipper}>
                  <td><span className={`rank ${i < 3 ? `r${i + 1}` : ""}`}>{i + 1}</span></td>
                  <td><b>{r.clipper}</b></td>
                  <td>{r.clips}</td>
                  <td>{r.best_score}%</td>
                  <td>{r.avg_score}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
