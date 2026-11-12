/** Convierte el link que pegó el usuario en algo que se pueda mostrar dentro de la página. */
export type Embed = {
  kind: "youtube" | "twitch" | "file" | "none";
  src: string;
  thumb?: string; // miniatura (solo YouTube): sirve de fondo difuminado sin cargar otro reproductor
};

export type Box = { x: number; y: number; w: number; h: number }; // en % del video

/** "1:23", "1:02:03" o "83" -> segundos */
export function toSeconds(v: string): number {
  const p = v.trim().split(":").map((n) => Number(n));
  if (!p.length || p.some((n) => !Number.isFinite(n) || n < 0)) return 0;
  return p.reduce((acc, n) => acc * 60 + n, 0);
}

export function parseEmbed(url: string, startSec = 0): Embed {
  const u = url.trim();
  if (!u) return { kind: "none", src: "" };

  const yt = u.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:[^#]*&)?v=|embed\/|shorts\/|live\/|v\/))([\w-]{11})/);
  if (yt) {
    const id = yt[1];
    const q = `autoplay=1&mute=1&controls=0&loop=1&playlist=${id}&modestbranding=1&rel=0&playsinline=1&disablekb=1&start=${Math.floor(startSec)}`;
    return { kind: "youtube", src: `https://www.youtube.com/embed/${id}?${q}`, thumb: `https://i.ytimg.com/vi/${id}/hqdefault.jpg` };
  }

  const host = typeof window !== "undefined" ? window.location.hostname : "localhost";
  const vod = u.match(/twitch\.tv\/(?:videos|[^/?#]+\/v)\/(\d+)/);
  if (vod) {
    const t = Math.floor(startSec);
    const time = t > 0 ? `&time=${Math.floor(t / 3600)}h${Math.floor((t % 3600) / 60)}m${t % 60}s` : "";
    return { kind: "twitch", src: `https://player.twitch.tv/?video=v${vod[1]}&parent=${host}&autoplay=true&muted=true${time}` };
  }
  const clip = u.match(/clips\.twitch\.tv\/([\w-]+)/) || u.match(/twitch\.tv\/[^/?#]+\/clip\/([\w-]+)/);
  if (clip) return { kind: "twitch", src: `https://clips.twitch.tv/embed?clip=${clip[1]}&parent=${host}&autoplay=true&muted=true` };

  if (/^https?:\/\/.+\.(mp4|webm|mov)(\?.*)?$/i.test(u)) return { kind: "file", src: u };

  return { kind: "none", src: "" }; // Kick y otros no se pueden incrustar
}

/** Lo que el worker calcula igual (render.py): mantén estas medidas en sincronía. */
export const SPLIT_TOP = 1312; // arriba tu cara/cámara; abajo (608 px) el gameplay completo en 16:9
export const SPLIT_BOT = 1920 - SPLIT_TOP;
export const ASPECT_CAM = 1080 / SPLIT_TOP; // panel de arriba (cámara)
export const ASPECT_GAME = 1080 / SPLIT_BOT; // panel de abajo (juego)
export const ASPECT_VERT = 9 / 16;

/** Alto (%) que le toca a un recuadro de ancho `w` (%) para tener la proporción `aspect` sobre un video 16:9. */
export const boxH = (w: number, aspect: number) => (w * 16) / (9 * aspect);
export const boxW = (h: number, aspect: number) => (h * 9 * aspect) / 16;

export function centerBox(aspect: number): Box {
  const h = 100;
  const w = Math.min(100, boxW(h, aspect));
  return { x: (100 - w) / 2, y: 0, w, h };
}

export const DEFAULT_CROP: Box = centerBox(ASPECT_VERT);
export const DEFAULT_CAM: Box = { x: 72, y: 43, w: 26, h: boxH(26, ASPECT_CAM) }; // esquina inferior derecha
export const GAME_BOX: Box = centerBox(ASPECT_GAME);

export const round2 = (b: Box): Box => ({ x: +b.x.toFixed(2), y: +b.y.toFixed(2), w: +b.w.toFixed(2), h: +b.h.toFixed(2) });
