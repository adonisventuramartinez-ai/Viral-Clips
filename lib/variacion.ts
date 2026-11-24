// Anti-"contenido duplicado": publicar el MISMO archivo con el MISMO texto en muchas páginas
// en el mismo segundo es la señal más clara de spam para Facebook y recorta (o anula) el alcance.
// Dos defensas sin tocar lo que el usuario escribió:
//   1) Escalonar: cada página sale unos segundos después de la anterior.
//   2) Los hashtags se reordenan distinto en cada página (el texto en sí no cambia).
// Desactivables en Vercel con ESCALONAR=off / VARIAR_TEXTO=off.

/** Generador pseudoaleatorio determinista (mulberry32) a partir de un texto. */
export function semilla(texto: string): () => number {
  let h = 1779033703 ^ texto.length;
  for (let i = 0; i < texto.length; i++) {
    h = Math.imul(h ^ texto.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Reordena los hashtags del texto de forma distinta para cada `clave` (p. ej. id de página).
 * Solo toca hashtags que están juntos al final de una línea; el resto del texto queda igual.
 */
export function variarHashtags(texto: string | null | undefined, clave: string): string {
  if (!texto) return texto || "";
  const rnd = semilla(clave);
  return texto
    .split("\n")
    .map((linea) => {
      const m = linea.match(/^(.*?)((?:\s*#[\p{L}\p{N}_]+){2,})\s*$/u);
      if (!m) return linea;
      const tags = m[2].match(/#[\p{L}\p{N}_]+/gu) || [];
      for (let i = tags.length - 1; i > 0; i--) {
        const j = Math.floor(rnd() * (i + 1));
        [tags[i], tags[j]] = [tags[j], tags[i]];
      }
      return `${m[1].trimEnd()}${m[1].trim() ? " " : ""}${tags.join(" ")}`;
    })
    .join("\n");
}

/**
 * Milisegundos a esperar antes de publicar en la página número `indice` (0 = sale ya).
 * Entre páginas hay 2-6 s al azar, pero el total nunca pasa de `maxTotalMs` (el cron tiene
 * un presupuesto de tiempo limitado).
 */
export function retrasoEscalonado(indice: number, total: number, rnd: () => number = Math.random, maxTotalMs = 20_000): number {
  if (indice <= 0 || total <= 1) return 0;
  const paso = Math.min(2000 + rnd() * 4000, maxTotalMs / Math.max(1, total - 1));
  return Math.round(paso * indice);
}

