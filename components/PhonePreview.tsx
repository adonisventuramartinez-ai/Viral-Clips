"use client";
import { Media, Region } from "@/components/CropPreview";
import { DEFAULT_CAM, DEFAULT_CROP, SPLIT_TOP, type Box, type Embed } from "@/lib/embed";
import { logoStyle, type Brand } from "@/lib/useBrand";

export type Layout = "crop" | "split" | "blur" | "duo";

const grad = { game: "linear-gradient(180deg,#7bb7ff,#4a7a3a)", cam: "linear-gradient(160deg,#ff6ad5,#8b3dff)" };

/** Teléfono 9:16 que muestra el video real del link con el mismo encuadre que hará el worker. */
export default function PhonePreview({ layout, embed, cropBox, camBox, brand, logoUrl }: { layout: Layout; embed: Embed; cropBox: Box | null; camBox: Box | null; brand?: Brand | null; logoUrl?: string | null }) {
  const live = embed.kind !== "none";
  const topPct = (SPLIT_TOP / 1920) * 100;
  const crop = cropBox ?? DEFAULT_CROP;
  const cam = camBox ?? DEFAULT_CAM;

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
        {zone({ top: `${topPct}%`, bottom: 0 }, grad.game, "Juego completo", <Media e={embed} />)}
      </>)}

      {layout === "duo" && (<>
        {zone({ top: 0, height: "50%" }, grad.cam, "Persona 1 (izquierda)", <Region e={embed} box={{ x: 0, y: 10.5, w: 50, h: 79 }} />)}
        {zone({ top: "50%", bottom: 0 }, grad.game, "Persona 2 (derecha)", <Region e={embed} box={{ x: 50, y: 10.5, w: 50, h: 79 }} />)}
      </>)}

      {layout === "blur" && (<>
        {zone({ inset: 0, filter: "blur(16px) brightness(.65)" }, grad.game, "", <Region e={embed} box={{ ...DEFAULT_CROP }} still />)}
        <div className="zone" style={{ top: "50%", left: 0, right: 0, transform: "translateY(-50%)", aspectRatio: "16 / 9", background: live ? "#000" : "linear-gradient(160deg,#4a7a3a,#2a4a6a)" }}>
          {live ? <Media e={embed} /> : "Video completo"}
        </div>
      </>)}

      {brand?.enabled && logoUrl && <img src={logoUrl} alt="" style={logoStyle(brand)} />}

      <div className="cap2" style={{ bottom: layout === "split" ? "31%" : layout === "duo" ? "46%" : "26%" }}>ASÍ <span style={{ color: "#ffe000" }}>SE VERÁN</span></div>
    </div>
  );
}

