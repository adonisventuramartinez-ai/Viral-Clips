// Lógica pura del Eliminador masivo (sin red): validación, filtros, respaldo y clasificación de errores.
// Se usa tanto en el servidor (ruta /api/eliminar) como en el navegador (componente Eliminador).

export type TipoContenido = "posts" | "reels" | "videos" | "fotos";

export const TIPOS: { id: TipoContenido; icono: string; texto: string; ayuda: string }[] = [
  { id: "reels", icono: "🎬", texto: "Reels", ayuda: "Reels publicados en la página" },
  { id: "videos", icono: "📹", texto: "Videos", ayuda: "Videos subidos (los reels pueden aparecer aquí también)" },
  { id: "fotos", icono: "🖼️", texto: "Fotos", ayuda: "Fotos subidas a la página" },
  { id: "posts", icono: "📝", texto: "Publicaciones", ayuda: "Todas las publicaciones del muro (texto, foto, video, enlace)" },
];

export interface ItemFb {
  id: string;
  texto: string;
  fecha: string; // ISO
  miniatura: string | null;
  enlace: string | null;
  duracion?: number | null;
}

export interface Filtro {
  texto: string; // contiene (sin distinguir mayúsculas)
  desde: string; // YYYY-MM-DD (incluida) o ""
  hasta: string; // YYYY-MM-DD (incluida) o ""
  masDeDias: number | null; // solo lo más viejo que N días
}

export const FILTRO_VACIO: Filtro = { texto: "", desde: "", hasta: "", masDeDias: null };

// Los IDs de Graph son números, o "paginaId_postId". Se validan antes de ponerlos en una URL.
export function idValido(id: unknown): id is string {
  return typeof id === "string" && /^\d{5,30}(_\d{5,30})?$/.test(id);
}

export function tipoValido(t: unknown): t is TipoContenido {
  return typeof t === "string" && TIPOS.some((x) => x.id === t);
}

// 4 = límite de la app · 17 = límite del usuario · 32 = límite de la página · 613 = demasiadas llamadas
export function esLimiteDeRitmo(codigo?: number): boolean {
  return codigo === 4 || codigo === 17 || codigo === 32 || codigo === 613;
}

// 190 token vencido · 102 sesión · 200/10 permisos · 459/464 cuenta con checkpoint
export function esFatal(codigo?: number): boolean {
  return codigo === 190 || codigo === 102 || codigo === 200 || codigo === 10 || codigo === 459 || codigo === 464;
}

export function filtrar(items: ItemFb[], f: Filtro, ahora: number = Date.now()): ItemFb[] {
  const q = f.texto.trim().toLowerCase();
  const desde = f.desde ? Date.parse(`${f.desde}T00:00:00`) : null;
  const hasta = f.hasta ? Date.parse(`${f.hasta}T23:59:59.999`) : null;
  const corte = f.masDeDias ? ahora - f.masDeDias * 86_400_000 : null;
  return items.filter((it) => {
    const t = Date.parse(it.fecha);
    if (q && !it.texto.toLowerCase().includes(q)) return false;
    if (desde !== null && !(t >= desde)) return false;
    if (hasta !== null && !(t <= hasta)) return false;
    if (corte !== null && !(t < corte)) return false;
    return true;
  });
}

export function trocear<T>(lista: T[], n: number): T[][] {
  const salida: T[][] = [];
  for (let i = 0; i < lista.length; i += Math.max(1, n)) salida.push(lista.slice(i, i + Math.max(1, n)));
  return salida;
}

// Lo que hay que escribir para confirmar. Incluye el número: no vale un "sí" distraído.
export const confirmacionEsperada = (n: number) => `ELIMINAR ${n}`;

export function confirmacionCorrecta(escrito: string, n: number): boolean {
  return n > 0 && escrito.trim().toUpperCase() === confirmacionEsperada(n);
}

// Respaldo en CSV de lo que se va a borrar (el archivo en sí no se puede respaldar desde aquí).
export function aCsv(items: ItemFb[]): string {
  const celda = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""').replace(/\r?\n/g, " ")}"`;
  const filas = items.map((i) => [i.id, i.fecha, i.texto, i.enlace || "", i.duracion ?? ""].map(celda).join(","));
  return ["id,fecha,texto,enlace,duracion_seg", ...filas].join("\n");
}

