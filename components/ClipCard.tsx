import type { Clip } from "@/lib/types";

export default function ClipCard({ clip }: { clip: Clip }) {
  const real = Boolean(clip.videoUrl);
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
          {clip.downloadUrl ? (
            <a className="btn sm" href={clip.downloadUrl} style={{ textAlign: "center" }}>Descargar</a>
          ) : (
            <button className="btn sm" disabled>Descargar</button>
          )}
          <button className="btn sm ghost" disabled title="Próximamente (Parte 5)">Pasar a narrado</button>
        </div>
      </div>
    </div>
  );
}
