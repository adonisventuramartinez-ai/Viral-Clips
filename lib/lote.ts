// Reparto de fechas para la programación en lote (corre en el navegador, así
// las horas se interpretan en la zona horaria del usuario).

export interface ReglasLote {
  inicio: Date;        // no se programa nada antes de este momento
  horas: string[];     // ["09:00", "18:30"]  → publicaciones por día
  dias: number[];      // días permitidos: 0=domingo … 6=sábado
  variacionMin: number; // ± minutos aleatorios para que no parezca un bot (0-30)
  semilla?: number;    // cambia el "azar" (botón Mezclar)
}

export function parsearHoras(texto: string): string[] {
  const set = new Set<string>();
  for (const parte of texto.split(/[,\s;]+/)) {
    const m = /^(\d{1,2}):(\d{2})$/.exec(parte.trim());
    if (!m) continue;
    const h = Number(m[1]), min = Number(m[2]);
    if (h > 23 || min > 59) continue;
    set.add(`${String(h).padStart(2, "0")}:${m[2]}`);
  }
  return [...set].sort();
}

function azar(i: number, semilla: number): number {
  const x = Math.sin((i + 1) * 12.9898 + semilla * 78.233) * 43758.5453;
  return x - Math.floor(x); // 0..1
}

export function repartirFechas(n: number, r: ReglasLote, ahoraMs: number = Date.now()): Date[] {
  if (n <= 0 || !r.horas.length || !r.dias.length) return [];
  const variacion = Math.max(0, Math.min(30, r.variacionMin));
  const minimo = Math.max(r.inicio.getTime(), ahoraMs + 2 * 60_000);
  const salida: Date[] = [];

  const dia = new Date(r.inicio);
  dia.setHours(0, 0, 0, 0);

  for (let d = 0; d < 800 && salida.length < n; d++, dia.setDate(dia.getDate() + 1)) {
    if (!r.dias.includes(dia.getDay())) continue;
    for (const hora of r.horas) {
      if (salida.length >= n) break;
      const [h, m] = hora.split(":").map(Number);
      const f = new Date(dia);
      f.setHours(h, m, 0, 0);
      const desplazamiento = Math.round((azar(salida.length, r.semilla ?? 0) * 2 - 1) * variacion);
      f.setMinutes(f.getMinutes() + desplazamiento);
      if (f.getTime() >= minimo) salida.push(f);
    }
  }
  return salida.sort((a, b) => a.getTime() - b.getTime());
}

// Variables de plantilla: {n} = número en el lote, {nombre} = nombre del archivo sin extensión, {descripcion} y {autor} = datos originales del video importado de TikTok
export function aplicarPlantilla(texto: string, n: number, nombreArchivo: string, descripcion = "", autor = ""): string {
  const base = nombreArchivo.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
  // Se usan funciones para que símbolos como "$" en la descripción no se interpreten
  return texto
    .replace(/\{n\}/g, () => String(n))
    .replace(/\{nombre\}/g, () => base)
    .replace(/\{descripcion\}/g, () => descripcion)
    .replace(/\{autor\}/g, () => autor);
}

