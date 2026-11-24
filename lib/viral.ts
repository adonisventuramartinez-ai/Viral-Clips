// Lógica de "Hacerlo viral" que usan la página y su API. Es copia fiel de worker/viral.py (title_score, combine) para que el
// puntaje se vea en vivo mientras escribes, y de los criterios de la lista "Antes de publicar".
import type { Viral } from "./types";

export const THUMB_STYLES = [
  { id: "amarillo", label: "Amarillo", color: "#ffe000" },
  { id: "rojo", label: "Rojo", color: "#ff2d4f" },
  { id: "blanco", label: "Blanco", color: "#ffffff" },
  { id: "centro", label: "Al centro", color: "#ffe000" },
] as const;
export const STYLE_IDS: string[] = THUMB_STYLES.map((s) => s.id);

const POWER = ["nadie", "increíble", "insólito", "se salió", "explot", "escándalo", "pelea", "descubr", "confes", "reveló", "reaccion", "no lo vas", "lo que pasó", "en vivo", "se armó", "tiraera", "verdad", "secreto", "viral", "locura", "tremendo", "épic"];
const RISK = ["estafador", "ladrón", "violador", "pedófilo", "asesino", "drogadicto", "corrupto", "puta", "maricón", "hijueputa"];
export const MIN_SCORE = 70; // = VIRAL_MIN_SCORE del worker (por defecto)

/** 0-100. Premia 25-65 caracteres, palabras de curiosidad, pregunta o número; castiga MAYÚSCULAS, signos de más y riesgos. */
export function titleScore(title: string): number {
  const t = String(title ?? "").split(/\s+/).filter(Boolean).join(" ");
  if (!t) return 0;
  let s = 40;
  const n = t.length;
  s += n >= 25 && n <= 65 ? 20 : (n >= 15 && n < 25) || (n > 65 && n <= 80) ? 8 : -15;
  const low = t.toLowerCase();
  s += Math.min(24, 8 * POWER.filter((w) => low.includes(w)).length);
  if (t.includes("?") || t.includes("¿")) s += 8;
  if (/\d/.test(t)) s += 5;
  const letters = Array.from(t).filter((c) => c.toLowerCase() !== c.toUpperCase());
  if (letters.length && letters.filter((c) => c === c.toUpperCase()).length / letters.length > 0.7 && n > 12) s -= 10;
  if (/[!?]{3,}/.test(t)) s -= 8;
  if (RISK.some((w) => low.includes(w))) s -= 25;
  return Math.max(0, Math.min(100, s));
}

export const risksIn = (...texts: (string | undefined | null)[]) => {
  const low = texts.map((t) => String(t ?? "")).join(" ").toLowerCase();
  return RISK.filter((w) => low.includes(w));
};

const durScore = (d: number) => (d >= 15 && d <= 60 ? 100 : (d >= 8 && d < 15) || (d > 60 && d <= 90) ? 70 : 40);

/** Cuánto aporta cada parte al puntaje: 50% el momento (IA), 20% título, 20% arranque, 10% duración. */
export function breakdown(modelScore: number, v: Viral | undefined, seconds: number, title?: string) {
  const ts = title !== undefined ? titleScore(title) : v?.titles?.[0]?.score ?? 0;
  const hs = v?.hook_score ?? 40;
  const parts = [
    { key: "momento", label: "Momento (lo que vio la IA)", pct: 50, value: Number(modelScore) || 0 },
    { key: "titulo", label: "Título", pct: 20, value: ts },
    { key: "arranque", label: "Arranque (primeras palabras)", pct: 20, value: hs },
    { key: "duracion", label: "Duración", pct: 10, value: durScore(seconds) },
  ].map((p) => ({ ...p, points: Math.round((p.value * p.pct) / 100) }));
  return { parts, total: Math.round(parts.reduce((a, p) => a + (p.value * p.pct) / 100, 0)) };
}

export type Check = { ok: boolean; warn?: boolean; text: string };

/** Lista "Antes de publicar": lo que falta o está flojo, en palabras simples. */
export function checklist(o: { title: string; hashtags: string[]; seconds: number; hasThumb: boolean; risks: string[]; total: number }): Check[] {
  const n = o.title.trim().length;
  return [
    { ok: o.hasThumb, text: o.hasThumb ? "Tiene miniatura" : "Le falta la miniatura (usa «Rehacer miniatura»)" },
    { ok: n >= 25 && n <= 65, warn: n >= 15 && n <= 80, text: `Título de ${n} caracteres (lo ideal es 25 a 65)` },
    { ok: o.hashtags.length >= 3 && o.hashtags.length <= 8, warn: o.hashtags.length > 0, text: `${o.hashtags.length} hashtags (lo ideal es 3 a 8)` },
    { ok: o.seconds >= 15 && o.seconds <= 60, warn: o.seconds >= 8 && o.seconds <= 90, text: `Dura ${o.seconds} s (lo ideal es 15 a 60)` },
    { ok: !o.risks.length, text: o.risks.length ? `Palabras de riesgo: ${o.risks.join(", ")}` : "Sin palabras de riesgo para Facebook" },
    { ok: o.total >= MIN_SCORE, warn: o.total >= 55, text: `Puntaje ${o.total}/100 (${MIN_SCORE} o más = listo)` },
  ];
}

/** Hashtags limpios: con #, sin espacios ni signos, de 3 a 30 caracteres, sin repetir, máximo `max`. */
export function cleanTags(input: unknown, max = 8): string[] {
  const raw = Array.isArray(input) ? input : String(input ?? "").split(/[\s,]+/);
  const out: string[] = [];
  for (const x of raw) {
    const t = "#" + String(x ?? "").replace(/^#+/, "").replace(/[^\p{L}\p{N}_]/gu, "");
    if (t.length >= 3 && t.length <= 30 && !out.some((o) => o.toLowerCase() === t.toLowerCase())) out.push(t);
    if (out.length >= max) break;
  }
  return out;
}

export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
