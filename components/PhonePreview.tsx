"use client";
import { Media, Region } from "@/components/CropPreview";
import { DEFAULT_CAM, DEFAULT_CROP, GAME_BOX, SPLIT_TOP, type Box, type Embed } from "@/lib/embed";

export type Layout = "crop" | "split" | "blur";

const grad = { game: "linear-gradient(180deg,#7bb7ff,#4a7a3a)", cam: "linear-gradient(160deg,#ff6ad5,#8b3dff)" };

/** Teléfono 9:16 que muestra el video real del link con el mismo encuadre que hará el worker. */
export default function PhonePreview({ layout, embed, cropBox, camBox }: { layout: Layout; embed: Embed; cropBox: Box | null; camBox: Box | null }) {
  const live = embed.kind !== "none";
  const topPct = (SPLIT_TOP / 1920) * 100;
  const fx = 0.5; // el worker usa CLIP_FOCUS_X (0.5 = centro)
  const crop = cropBox ?? DEFAULT_CROP;
  const cam = camBox ?? DEFAULT_CAM;
  const game = { ...GAME_BOX, x: (100 - GAME_BOX.w) * fx };

  const zone = (style: React.CSSProperties, bg: string, label: string, child?: React.ReactNode) => (
    <div className="zone" style={{ ...style, background: live ? "#000" : bg }}>
      {live ? child : label}
    </div>
  );

  return (
    <div className="phone">
      <span className="badge">VISTA PREVIA</span>

      {layout === "crop" && zone({ inset: 0 }, grad.game, "Recorte vertical del juego", <Region e={embed} box={crop} />)}

      {layout === "split" && (<>
        {zone({ top: 0, height: `${topPct}%` }, grad.cam, "Cámara", <Region e={embed} box={cam} />)}
        {zone({ top: `${topPct}%`, bottom: 0 }, grad.game, "Juego", <Region e={embed} box={game} />)}
      </>)}

      {layout === "blur" && (<>
        {zone({ inset: 0, filter: "blur(16px) brightness(.65)" }, grad.game, "", <Region e={embed} box={{ ...DEFAULT_CROP }} still />)}
        <div className="zone" style={{ top: "50%", left: 0, right: 0, transform: "translateY(-50%)", aspectRatio: "16 / 9", background: live ? "#000" : "linear-gradient(160deg,#4a7a3a,#2a4a6a)" }}>
          {live ? <Media e={embed} /> : "Video completo"}
        </div>
      </>)}

      <div className="cap2" style={{ bottom: layout === "split" ? "50%" : "26%" }}>ASÍ <span style={{ color: "#ffe000" }}>SE VERÁN</span></div>
    </div>
  );
}
