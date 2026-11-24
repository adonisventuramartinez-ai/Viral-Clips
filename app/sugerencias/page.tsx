"use client";
import { useState } from "react";
import { postHub, useHub } from "@/lib/useHub";
import { ago } from "@/components/CommunityFeed";

type Row = { id: string; author: string | null; body: string; votes: number; created_at: string };

export default function Sugerencias() {
  const { items, error, reload } = useHub<Row>("suggestions");
  const [err, setErr] = useState("");
  async function send(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = e.currentTarget;
    const e2 = await postHub("suggestions", Object.fromEntries(new FormData(f)));
    setErr(e2 ?? ""); if (!e2) { f.reset(); reload(); }
  }
  return (
    <>
      <h1>💡 Sugerencias</h1>
      <p className="sub">Dinos qué te gustaría ver. Vota las que más te gusten.</p>
      <form className="card" onSubmit={send} style={{ maxWidth: 640, marginBottom: 18 }}>
        <input name="author" placeholder="Tu nombre (opcional)" maxLength={40} />
        <textarea name="body" rows={3} placeholder="Mi idea es…" required maxLength={500} style={{ marginTop: 10 }} />
        <button className="btn sm" style={{ marginTop: 10 }}>Enviar</button>
        {(err || error) && <div className="banner" style={{ marginTop: 12, marginBottom: 0 }}>{err || error}</div>}
      </form>
      <div style={{ display: "grid", gap: 10, maxWidth: 640 }}>
        {(items ?? []).map((s) => (
          <div className="card" key={s.id} style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <button className="btn ghost sm" onClick={async () => { await postHub("suggestions", { vote: true, id: s.id }); reload(); }}>▲ {s.votes}</button>
            <div><div>{s.body}</div><small style={{ color: "var(--muted)" }}>{s.author || "anónimo"} · {ago(s.created_at)}</small></div>
          </div>
        ))}
      </div>
    </>
  );
}
