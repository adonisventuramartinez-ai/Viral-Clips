"use client";
import { useCallback, useEffect, useState } from "react";

export type Subs = { text: string; active: string; outline: string; size: number; outline_w: number; upper: boolean; pop: boolean; offset: number };
export type Brand = { enabled: boolean; pos: string; size: number; opacity: number; file?: string; subs?: Subs; hook?: boolean; hook_sec?: number };

/** Estilos de subtítulos listos (los mismos valores los usa el worker). Fuente: DejaVu Sans Bold. */
export const SUB_PRESETS: Record<string, { label: string; v: Subs }> = {
  classic: { label: "Clásico (blanco + amarillo)", v: { text: "FFFFFF", active: "FFE000", outline: "000000", size: 86, outline_w: 7, upper: true, pop: true, offset: 0 } },
  neon:    { label: "Neón (cian + borde morado)", v: { text: "FFFFFF", active: "2EE6D6", outline: "8B3DFF", size: 90, outline_w: 9, upper: true, pop: true, offset: 0 } },
  green:   { label: "Verde grande", v: { text: "FFFFFF", active: "00E676", outline: "000000", size: 100, outline_w: 10, upper: true, pop: true, offset: 0 } },
  fire:    { label: "Fuego (naranja)", v: { text: "FFFFFF", active: "FF7A00", outline: "000000", size: 92, outline_w: 8, upper: true, pop: true, offset: 0 } },
  minimal: { label: "Minimalista (sin efecto)", v: { text: "FFFFFF", active: "FFFFFF", outline: "000000", size: 70, outline_w: 4, upper: false, pop: false, offset: 0 } },
};

/** Logo guardado (Ajustes > Logo) con su URL temporal. */
export function useBrand() {
  const [brand, setBrand] = useState<Brand | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const load = useCallback(() => {
    fetch("/api/brand", { cache: "no-store" }).then((r) => r.json()).then((j) => { setBrand(j.settings ?? null); setLogoUrl(j.logoUrl ?? null); }).catch(() => {});
  }, []);
  useEffect(load, [load]);
  return { brand, logoUrl, reload: load };
}

/** Estilo CSS del logo sobre el teléfono, igual que lo calcula el worker (render.py). */
export const toHash = (c: string) => `#${c.replace("#", "")}`;

export function logoStyle(b: Brand): React.CSSProperties {
  const [v, h] = [b.pos[0], b.pos[1]];
  const m = (110 / 1920) * 100;
  const s: React.CSSProperties = { position: "absolute", width: `${b.size}%`, opacity: b.opacity / 100, zIndex: 5, pointerEvents: "none" };
  if (v === "b") s.bottom = `${m}%`; else s.top = `${(60 / 1920) * 100}%`;
  if (h === "c") { s.left = "50%"; s.transform = "translateX(-50%)"; } else if (h === "l") s.left = `${(40 / 1080) * 100}%`; else s.right = `${(40 / 1080) * 100}%`;
  return s;
}
