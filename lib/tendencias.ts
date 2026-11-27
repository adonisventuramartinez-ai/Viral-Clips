// Tendencias del día (Google Trends, RSS público y gratuito, por país).
// Facebook no ofrece una API pública de hashtags virales: esto es una señal de lo que la gente busca HOY.

export interface Tendencia {
  termino: string;
  trafico: string; // "200+", "5K+"…
  hashtag: string | null; // null si no se puede convertir en un hashtag decente
  relacionada: boolean;   // coincide con palabras de la descripción del video
}

const decodificar = (s: string) =>
  s.replace(/<!\[CDATA\[(.*?)\]\]>/gs, "$1")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#0?39;/g, "'")
    .trim();

function sinAcentos(s: string) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export function aHashtag(termino: string): string | null {
  const limpio = sinAcentos(termino).replace(/[^\p{L}\p{N}\s]/gu, "").trim();
  if (!limpio) return null;
  const palabras = limpio.split(/\s+/);
  if (palabras.length > 3) return null;
  const h = palabras.map((p) => p.toLowerCase()).join("");
  return h.length >= 3 && h.length <= 28 ? "#" + h : null;
}

export function parsearTrendsRss(xml: string, descripcion = ""): Tendencia[] {
  const palabras = new Set(
    sinAcentos(descripcion.toLowerCase()).split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 4)
  );
  const salida: Tendencia[] = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const bloque = m[1];
    const t = /<title>([\s\S]*?)<\/title>/.exec(bloque);
    if (!t) continue;
    const termino = decodificar(t[1]);
    if (!termino || termino.length > 60) continue;
    const tr = /<ht:approx_traffic>([\s\S]*?)<\/ht:approx_traffic>/.exec(bloque);
    const claves = sinAcentos(termino.toLowerCase()).split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 4);
    salida.push({
      termino,
      trafico: tr ? decodificar(tr[1]) : "",
      hashtag: aHashtag(termino),
      relacionada: claves.some((w) => palabras.has(w)),
    });
  }
  // Las relacionadas con el video primero; el resto conserva el orden de Google
  return salida.sort((a, b) => Number(b.relacionada) - Number(a.relacionada)).slice(0, 15);
}

