"use client";
import { useHub } from "@/lib/useHub";

type Row = { id: string; name: string; amount: number | null; message: string | null };
const DONATE = process.env.NEXT_PUBLIC_DONATE_URL || "";

export default function Donadores() {
  const { items, error } = useHub<Row>("donors");
  return (
    <>
      <h1>♥ Donadores</h1>
      <p className="sub">Gracias a ellos la web sigue online. Agrega donadores desde Supabase (tabla <code>donors</code>).</p>
      {DONATE && <a href={DONATE} target="_blank" rel="noreferrer" className="pill green" style={{ marginBottom: 18 }}>♥ Donar</a>}
      {error && <div className="banner">{error}</div>}
      <div className="grid3">
        {(items ?? []).map((d) => (
          <div className="card" key={d.id}>
            <b style={{ fontSize: 17 }}>{d.name}</b>
            {d.amount != null && <div className="viral" style={{ margin: "4px 0" }}>${d.amount}</div>}
            {d.message && <small style={{ color: "var(--muted)" }}>{d.message}</small>}
          </div>
        ))}
        {items?.length === 0 && <div className="card" style={{ color: "var(--muted)" }}>Todavía no hay donadores. ¡Sé el primero!</div>}
      </div>
    </>
  );
}
