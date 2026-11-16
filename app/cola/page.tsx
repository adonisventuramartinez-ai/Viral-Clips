"use client";
import { useCallback, useEffect, useState } from "react";
import SwitchCard from "@/components/SwitchCard";

type Post = { id: string; network: string; status: string; scheduled_at: string; error: string | null; published_at: string | null; clips: { title: string; viral_score: number } | null };
type Info = { auto_queue?: boolean; networks?: string[] };

const NET: Record<string, string> = { facebook: "Facebook", instagram: "Instagram", youtube: "YouTube Shorts" };
const ST: Record<string, string> = { queued: "⏳ En cola", publishing: "📤 Publicando", published: "✅ Publicado", error: "⚠️ Error", cancelled: "⛔ Cancelado" };

export default function Cola() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [info, setInfo] = useState<Info>({});
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const load = useCallback(async () => {
    const r = await fetch("/api/posts").catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) return setErr(j?.error ?? "No se pudo conectar");
    setErr(""); setPosts(j.posts); setInfo(j.worker ?? {});
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  async function act(id: string, body: Record<string, unknown>) {
    setNote("");
    const r = await fetch(`/api/posts/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) setNote(j?.error ?? "No se pudo");
    load();
  }
  function move(p: Post) {
    const v = prompt("Nueva fecha y hora (AAAA-MM-DD HH:MM, tu hora)", new Date(p.scheduled_at).toLocaleString("sv").slice(0, 16));
    if (v) act(p.id, { scheduled_at: new Date(v.replace(" ", "T")).toISOString() });
  }

  const nets = info.networks ?? [];
  const up = posts.filter((p) => p.status === "queued" || p.status === "publishing");
  const rest = posts.filter((p) => !up.includes(p)).reverse();
  const row = (p: Post) => (
    <div key={p.id} className="card" style={{ display: "flex", gap: 12, justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
      <div style={{ minWidth: 220 }}>
        <b>{p.clips?.title ?? "(clip borrado)"}</b>
        <div><small style={{ color: "var(--muted)" }}>{NET[p.network] ?? p.network} · {new Date(p.published_at ?? p.scheduled_at).toLocaleString()}</small></div>
        {p.error && <small style={{ color: "#ef4444" }}>{p.error}</small>}
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <span>{ST[p.status] ?? p.status}</span>
        {p.status === "queued" && <><button className="btn sm ghost" onClick={() => move(p)}>🕐 Mover</button><button className="btn sm ghost" onClick={() => act(p.id, { action: "cancel" })}>Cancelar</button></>}
        {(p.status === "error" || p.status === "cancelled") && <button className="btn sm ghost" onClick={() => act(p.id, { action: "retry" })}>↻ Reintentar</button>}
      </div>
    </div>
  );
  return (
    <>
      <h1>🗓 Cola de publicación</h1>
      <p className="sub">Lo que el worker publica solo a su hora. Los clips entran aquí cuando el área viral los marca como listos.</p>
      {err && <div className="banner">{err}</div>}
      <SwitchCard
        name="auto_queue"
        title="Cola automática"
        desc="Programa solos, a la mejor hora, los clips que salen «listos» en tus redes conectadas. Si tienes «Aprobar yo cada clip» en Hacerlo viral, solo entran los que aprobaste."
        confirmOn="Al encender, los clips «listos» se programan solos en tus redes conectadas y se publican a su hora. ¿Encender la cola automática?"
      />
      {!err && (
        <div className="banner" style={{ background: "transparent" }}>
          Redes conectadas: {nets.length ? nets.map((n) => NET[n] ?? n).join(", ") : "ninguna (conéctalas en Conectar cuentas)"}
        </div>
      )}
      {note && <div className="banner">{note}</div>}
      <h3>Próximas ({up.length})</h3>
      <div style={{ display: "grid", gap: 8 }}>{up.length ? up.map(row) : <small style={{ color: "var(--muted)" }}>Nada en cola.</small>}</div>
      <h3 style={{ marginTop: 24 }}>Historial</h3>
      <div style={{ display: "grid", gap: 8 }}>{rest.length ? rest.map(row) : <small style={{ color: "var(--muted)" }}>Aún vacío.</small>}</div>
    </>
  );
}
