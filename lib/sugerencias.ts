// Sugerencias de título y hashtags para un video importado. Sin servicios externos: se calcula
// a partir de la descripción original (palabras clave, hashtags propios) + etiquetas de alcance.
// OJO: no consulta tendencias en vivo; son combinaciones probadas, no datos del momento.

const PARADA = new Set(
  ("para pero como esto esta este estos estas esos esas desde hasta entre sobre porque cuando donde quien cual " +
    "todo todos toda todas muy mas menos algo nada solo tambien aqui alli ahora siempre nunca cada otra otros " +
    "with that this from have your what when they them then been were will just like about into over more some " +
    "video reel tiktok instagram follow sigueme link bio").split(/\s+/)
);

// Etiquetas de alcance para Reels/video corto (en orden de prioridad)
const GENERICAS = ["#reels", "#viral", "#fyp", "#parati", "#videoviral", "#tendencia", "#facebookreels", "#explorar", "#foryou", "#trending"];

function sinAcentos(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

/** Quita hashtags, menciones, enlaces y espacios repetidos. */
export function limpiarTexto(txt: string): string {
  return (txt || "")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[#@][\p{L}\p{N}_.]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function recortar(s: string, max: number): string {
  if (s.length <= max) return s;
  const corte = s.slice(0, max - 1);
  const ultimo = corte.lastIndexOf(" ");
  return (ultimo > max * 0.5 ? corte.slice(0, ultimo) : corte).replace(/[,;:\-–\s]+$/, "") + "…";
}

function mayus(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

export function sugerirTitulos(descripcion: string, autor = "", max = 6): string[] {
  const base = limpiarTexto(descripcion);
  const primera = (base.split(/(?<=[.!?])\s+|\n/)[0] || "").replace(/[.!?]+$/, "").trim();
  const tema = mayus(recortar(primera || base, 70));
  const salida: string[] = [];
  const add = (t: string) => {
    const x = t.replace(/\s+/g, " ").trim();
    if (x && x.length <= 120 && !salida.some((y) => y.toLowerCase() === x.toLowerCase())) salida.push(x);
  };

  if (tema) {
    add(tema);
    add(`😱 ${tema}`);
    add(`${tema} 👇`);
    add(`Mira esto: ${tema}`);
    add(`No vas a creer esto… ${tema}`);
    add(`🔥 ${tema} (hasta el final)`);
  } else {
    add("😱 No vas a creer esto");
    add("Mira este video hasta el final 👇");
    add("🔥 Esto se está haciendo viral");
  }
  if (autor && salida.length < max) add(`${tema || "Video"} — vía @${autor.replace(/^@/, "")}`);
  return salida.slice(0, max);
}

export function sugerirHashtags(descripcion: string, autor = "", max = 12): { recomendados: string[]; todos: string[] } {
  const propios: string[] = [];
  for (const m of (descripcion || "").matchAll(/#([\p{L}\p{N}_]{2,30})/gu)) {
    const h = "#" + m[1].toLowerCase();
    if (!propios.includes(h)) propios.push(h);
  }

  // Palabras clave por frecuencia
  const cuenta = new Map<string, number>();
  for (const w of limpiarTexto(descripcion).toLowerCase().split(/[^\p{L}\p{N}]+/u)) {
    if (w.length < 5 || w.length > 20 || /^\d+$/.test(w) || PARADA.has(sinAcentos(w))) continue;
    cuenta.set(w, (cuenta.get(w) || 0) + 1);
  }
  const claves = [...cuenta.entries()].sort((a, b) => b[1] - a[1] || b[0].length - a[0].length).map(([w]) => "#" + sinAcentos(w));

  const orden: string[] = [];
  const add = (h: string) => {
    if (h.length > 2 && !orden.includes(h) && !orden.some((o) => o.toLowerCase() === h.toLowerCase())) orden.push(h);
  };
  propios.slice(0, 4).forEach(add);
  claves.slice(0, 3).forEach(add);
  GENERICAS.forEach(add);
  propios.slice(4).forEach(add);
  claves.slice(3).forEach(add);

  const todos = orden.slice(0, max);
  // En Facebook funcionan mejor pocos hashtags (3–5): se preseleccionan 5
  const recomendados = todos.slice(0, 5);
  return { recomendados, todos };
}

/** Une descripción + hashtags elegidos para usarlo como mensaje del post. */
export function armarMensaje(descripcion: string, hashtags: string[]): string {
  const texto = limpiarTexto(descripcion);
  const tags = [...new Set(hashtags)].join(" ");
  return [texto, tags].filter(Boolean).join("\n\n").slice(0, 2000);
}

