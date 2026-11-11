"use client";
import { useHub } from "@/lib/useHub";

type Row = { id: string; name: string; channel_url: string | null; schedule: string | null };

export default function Programas() {
  const { items, error } = useHub<Row>("programs");
  return (
    <>
      <h1>📺 Programas</h1>
      <p className="sub">Directorio de programas y canales para clipear. Agrégalos en Supabase (tabla <code>programs</code>).</p>
      {error && <div className="banner">{error}</div>}
      <div className="grid3">
        {(items ?? []).map((p) => (
          <div className="card" key={p.id}>
            <b style={{ fontSize: 17 }}>{p.name}</b>
            {p.schedule && <div style={{ color: "var(--muted)", margin: "4px 0" }}>{p.schedule}</div>}
            {p.channel_url && <a className="viral" href={p.channel_url} target="_blank" rel="noreferrer">Ver canal →</a>}
          </div>
        ))}
        {items?.length === 0 && <div className="card" style={{ color: "var(--muted)" }}>Aún no hay programas cargados.</div>}
      </div>
    </>
  );
}
