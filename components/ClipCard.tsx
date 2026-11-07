import type { Clip } from "@/lib/types";

export default function ClipCard({ clip }: { clip: Clip }) {
  return (
    <div className="clip">
      <div className="v" style={{ background: clip.thumb }}>
        <span className="tag">{clip.start}–{clip.end}</span>
        <span className="play">▶</span>
        <div className="cap">{clip.captions}</div>
      </div>
      <div className="meta">
        <p>{clip.title}</p>
        <small><span className="viral">{clip.score}% viral</span> · {clip.sizeMb} MB</small>
        <div className="acts">
          <button className="btn sm">Descargar</button>
          <button className="btn sm ghost">Pasar a narrado</button>
        </div>
      </div>
    </div>
  );
}
