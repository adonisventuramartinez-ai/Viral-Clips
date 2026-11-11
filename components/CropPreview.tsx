"use client";
import { useRef } from "react";
import type { CSSProperties } from "react";
import { boxH, type Box, type Embed } from "@/lib/embed";

const fill: CSSProperties = { position: "absolute", inset: 0, width: "100%", height: "100%", border: 0, pointerEvents: "none", objectFit: "cover" };

/** El video (o su miniatura) llenando el contenedor. */
export function Media({ e, still = false }: { e: Embed; still?: boolean }) {
  if (still && e.thumb) return <img src={e.thumb} alt="" style={fill} />;
  if (e.kind === "file") return <video src={e.src} muted loop autoPlay playsInline style={fill} />;
  if (e.kind === "none") return null;
  return <iframe src={e.src} allow="autoplay; encrypted-media; picture-in-picture" tabIndex={-1} style={fill} />;
}

/** Muestra SOLO la zona `box` del video, estirada para llenar el contenedor (que debe tener la misma proporción que el recuadro). */
export function Region({ e, box, still = false }: { e: Embed; box: Box; still?: boolean }) {
  return (
    <div style={{ position: "absolute", left: `${(-box.x / box.w) * 100}%`, top: `${(-box.y / box.h) * 100}%`, width: `${10000 / box.w}%`, aspectRatio: "16 / 9" }}>
      <Media e={e} still={still} />
    </div>
  );
}

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

/** Video completo con un recuadro que se arrastra y se agranda desde la esquina (mantiene la proporción `aspect`). */
export default function CropPreview({ embed, box, aspect, onChange }: { embed: Embed; box: Box; aspect: number; onChange: (b: Box) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef<{ mode: "move" | "resize"; sx: number; sy: number; start: Box } | null>(null);

  const down = (mode: "move" | "resize") => (ev: React.PointerEvent) => {
    ev.preventDefault();
    ev.stopPropagation();
    (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId);
    drag.current = { mode, sx: ev.clientX, sy: ev.clientY, start: box };
  };
  const move = (ev: React.PointerEvent) => {
    const d = drag.current;
    const el = ref.current;
    if (!d || !el) return;
    const r = el.getBoundingClientRect();
    const dx = ((ev.clientX - d.sx) / r.width) * 100;
    const dy = ((ev.clientY - d.sy) / r.height) * 100;
    if (d.mode === "move") {
      onChange({ ...d.start, x: clamp(d.start.x + dx, 0, 100 - d.start.w), y: clamp(d.start.y + dy, 0, 100 - d.start.h) });
    } else {
      const maxW = Math.min(100 - d.start.x, ((100 - d.start.y) * 9 * aspect) / 16);
      const w = clamp(d.start.w + dx, 8, Math.max(8, maxW));
      onChange({ ...d.start, w, h: boxH(w, aspect) });
    }
  };
  const up = () => { drag.current = null; };

  return (
    <div ref={ref} style={{ position: "relative", width: "100%", aspectRatio: "16 / 9", background: "#000", overflow: "hidden", userSelect: "none", touchAction: "none", borderRadius: 10 }}>
      <Media e={embed} />
      <div
        onPointerDown={down("move")}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        style={{ position: "absolute", left: `${box.x}%`, top: `${box.y}%`, width: `${box.w}%`, height: `${box.h}%`, border: "2px solid #2ee6d6", boxShadow: "0 0 0 9999px rgba(0,0,0,.6)", cursor: "move", touchAction: "none" }}
      >
        <div onPointerDown={down("resize")} style={{ position: "absolute", right: -2, bottom: -2, width: 22, height: 22, background: "#2ee6d6", cursor: "nwse-resize", touchAction: "none", borderTopLeftRadius: 6 }} />
      </div>
    </div>
  );
}
