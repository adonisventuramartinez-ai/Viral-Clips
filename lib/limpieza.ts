// Limpieza automática de Supabase Storage.
//
// El plan gratuito de Supabase da 1 GB. Sin esto los videos de publicaciones ya
// publicadas / canceladas (y los que se subieron pero nunca se programaron)
// se quedan para siempre y el almacenamiento se llena hasta que las subidas fallan.
//
// Un archivo se BORRA solo si cumple las tres cosas:
//   1. tiene más de LIMPIEZA_DIAS días (por defecto 2): margen para subidas en curso;
//   2. ningún post pendiente / publicando / con error lo usa (el de "error" se
//      conserva para poder reintentar; las series recurrentes comparten archivo);
//   3. no es un video importado de TikTok que sigue "listo" (aún sin programar),
//      ni la miniatura de una importación existente.
// Para apagarla: LIMPIEZA_STORAGE=off en Vercel.

import { supabaseAdmin, BUCKET } from "./db";

const PAGINA = 1000;
const MAX_BORRADOS_POR_CORRIDA = 300;

interface Objeto {
  path: string;
  creado: number;
}

async function listarCarpeta(prefijo: string): Promise<{ archivos: Objeto[]; carpetas: string[] }> {
  const archivos: Objeto[] = [];
  const carpetas: string[] = [];
  for (let offset = 0; offset < 20_000; offset += PAGINA) {
    const { data, error } = await supabaseAdmin.storage
      .from(BUCKET)
      .list(prefijo, { limit: PAGINA, offset, sortBy: { column: "name", order: "asc" } });
    if (error) throw error;
    for (const it of data || []) {
      const ruta = prefijo ? `${prefijo}/${it.name}` : it.name;
      if (it.id === null || it.id === undefined) carpetas.push(ruta); // las carpetas no traen id
      else archivos.push({ path: ruta, creado: new Date(it.created_at || it.updated_at || Date.now()).getTime() });
    }
    if (!data || data.length < PAGINA) break;
  }
  return { archivos, carpetas };
}

async function rutasProtegidas(): Promise<Set<string>> {
  const protegidas = new Set<string>();

  const { data: posts, error: e1 } = await supabaseAdmin
    .from("posts_programados")
    .select("archivo_url")
    .in("estado", ["pendiente", "publicando", "error"])
    .limit(20_000);
  if (e1) throw e1;
  for (const p of posts || []) if (p.archivo_url) protegidas.add(p.archivo_url);

  const { data: imps, error: e2 } = await supabaseAdmin
    .from("importaciones")
    .select("archivo_url, miniatura_path, estado")
    .limit(20_000);
  if (e2) throw e2;
  for (const i of imps || []) {
    if (i.miniatura_path) protegidas.add(i.miniatura_path);
    if (i.archivo_url && i.estado === "listo") protegidas.add(i.archivo_url);
  }
  return protegidas;
}

export interface ResumenLimpieza {
  revisados: number;
  borrados: number;
}

export async function limpiarStorage(ahoraMs: number = Date.now()): Promise<ResumenLimpieza> {
  const dias = Math.max(1, Number(process.env.LIMPIEZA_DIAS) || 2);
  const limite = ahoraMs - dias * 86_400_000;

  const protegidas = await rutasProtegidas();
  const raiz = await listarCarpeta("");

  const candidatos: Objeto[] = [...raiz.archivos];
  for (const carpeta of raiz.carpetas.slice(0, 200)) {
    candidatos.push(...(await listarCarpeta(carpeta)).archivos);
  }

  const aBorrar = candidatos
    .filter((o) => o.creado < limite && !protegidas.has(o.path))
    .slice(0, MAX_BORRADOS_POR_CORRIDA);

  let borrados = 0;
  for (let i = 0; i < aBorrar.length; i += 100) {
    const lote = aBorrar.slice(i, i + 100).map((o) => o.path);
    const { error } = await supabaseAdmin.storage.from(BUCKET).remove(lote);
    if (error) throw error;
    borrados += lote.length;
  }
  return { revisados: candidatos.length, borrados };
}

