"use client";
import { useEffect, useState } from "react";

type Item = { id: string; title: string; seconds: number; clipper: string; source: string | null; createdAt: string; videoUrl: string | null; score: number };

export function ago(iso: string) {
  const m = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 60) return `hace ${m} min`;
  const h = Math.round(m / 60);
  return h < 24 ? `hace ${h} h` : `hace ${Math.round(h / 24)} d`;
}
const dur = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function CommunityFeed({ kind = "feed", limit = 12 }: { kind?: "feed" | "top"; limit?: number }) {
  const [items, setItems] = useState<Item[] | null>(null);
  useEffect(() => {
    fetch(`/api/hub/${kind}?limit=${limit}`).then((r) => r.json()).then((j) => setItems(j.items ?? [])).catch(() => setItems([]));
  }, [kind, limit]);

  if (items === null) return <small style={{ color: "var(--muted)" }}>Cargando…</small>;
  if (!items.length) return <small style={{ color: "var(--muted)" }}>Todavía no hay clips públicos. ¡Creá el primero!</small>;
  return (
    <div className="feed">
      {items.map((c) => (
        <div className="fc" key={c.id}>
          <div className="th">
            {c.videoUrl && <video src={c.videoUrl} muted playsInline preload="metadata" onMouseEnter={(e) => e.currentTarget.play().catch(() => {})} onMouseLeave={(e) => e.currentTarget.pause()} />}
            <i>{dur(c.seconds)}</i>
          </div>
          <p>{c.clipper}</p>
          <small>{c.title}</small>
          <small>{c.source ? `${c.source} · ` : ""}{ago(c.createdAt)}</small>
        </div>
      ))}
    </div>
  );
}
