"use client";
import { useState } from "react";
import type { Clip } from "@/lib/types";

const TAGS = "#fyp #viral #clips #streamer";

export default function ClipCard({ clip, onDeleted }: { clip: Clip; onDeleted?: (id: string) => void }) {
  const real = Boolean(clip.videoUrl);
  const [busy, setBusy] = useState(false);
  const [pub, setPub] = useState(clip.isPublic ?? true);
  const [copied, setCopied] = useState(false);

  async function remove() {
    if (!confirm("¿Seguro que quieres eliminar este clip para siempre?")) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/clips/${clip.id}`, { method: "DELETE" });
      if (res.ok) return onDeleted ? onDeleted(clip.id) : window.location.reload();
      const j = await res.json().catch(() => ({}));
      alert(j.error || "Error al eliminar el clip");
    } catch {
      alert("Error de conexión");
    }
    setBusy(false);
  }

  async function togglePublic() {
    const next = !pub;
    setPub(next);
    const res = await fetch(`/api/clips/${clip.id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_public: next }),
    }).catch(() => null);
    if (!res || !res.ok) setPub(!next);
  }

  async function copyText() {
    try {
      await navigator.clipboard.writeText(`${clip.title} ${TAGS}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* sin permiso de portapapeles */ }
  }

  return (
    <div className="clip">
      <div className="v" style={real ? { background: "#000", padding: 0 } : { background: clip.thumb }}>
        {real ? (
          <video src={clip.videoUrl} controls playsInline preload="metadata" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <>
            <span className="tag">{clip.start}–{clip.end}</span>
            <span className="play">▶</span>
            <div className="cap">{clip.captions}</div>
          </>
        )}
      </div>
      <div className="meta">
        <p>{clip.title}</p>
        <small><span className="viral">{clip.score}% viral</span> · {clip.sizeMb} MB · {clip.start}–{clip.end}</small>
        {clip.reason && <small style={{ display: "block", marginTop: 6, fontFamily: "inherit" }}>{clip.reason}</small>}

        <div className="acts">
          {clip.downloadUrl
            ? <a className="btn sm" href={clip.downloadUrl} style={{ textAlign: "center" }}>Descargar</a>
            : <button className="btn sm" disabled>Descargar</button>}
          <button className="btn sm ghost" onClick={copyText}>{copied ? "¡Copiado!" : "Copiar título + hashtags"}</button>
          <button className="btn sm ghost" onClick={togglePublic} title="Si está público aparece en el Top y el feed de la comunidad">
            {pub ? "🌐 Público" : "🔒 Privado"}
          </button>
          <button className="btn sm" onClick={remove} disabled={busy} style={{ background: "#ef4444", color: "#fff", border: "none" }}>
            {busy ? "Eliminando…" : "Eliminar clip"}
          </button>
        </div>
      </div>
    </div>
  );
}
