import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin, BUCKET } from "@/lib/db";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";
import { clasificarEntrada } from "@/lib/tiktok";
import { despacharWorker } from "@/lib/github";

export const dynamic = "force-dynamic";

const MAX_URLS = 30;
const MAX_ACTIVAS = 40;

// GET: importaciones del usuario (con URL firmada para la miniatura)
export async function GET(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  const { data, error } = await supabaseAdmin
    .from("importaciones")
    .select("id, tipo, url, estado, titulo, descripcion, autor, duracion, bytes, archivo_url, miniatura_path, videos, error, creado_en, terminado_en")
    .eq("propietario_fb_id", sesion.sub)
    .order("id", { ascending: false })
    .limit(150);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const filas = data || [];
  const rutas = filas.map((f: any) => f.miniatura_path).filter(Boolean) as string[];
  const firmadas: Record<string, string> = {};
  if (rutas.length) {
    const { data: urls } = await supabaseAdmin.storage.from(BUCKET).createSignedUrls(rutas, 3600);
    for (const u of urls || []) if (u.path && u.signedUrl) firmadas[u.path] = u.signedUrl;
  }
  return NextResponse.json({
    importaciones: filas.map((f: any) => ({ ...f, miniatura: f.miniatura_path ? firmadas[f.miniatura_path] || null : null })),
  });
}

// POST { urls: [...] }  → crea trabajos y despierta el worker
// POST { accion: "procesar" } → solo despierta el worker (si quedó algo pendiente)
export async function POST(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  try {
    const body = await req.json();

    if (body.accion === "procesar") {
      const d = await despacharWorker();
      return NextResponse.json({ despacho: d }, { status: d.ok ? 200 : 502 });
    }

    const crudas: string[] = Array.isArray(body.urls) ? body.urls.map(String) : [];
    if (!crudas.length || crudas.length > MAX_URLS) {
      return NextResponse.json({ error: `Pega entre 1 y ${MAX_URLS} enlaces` }, { status: 400 });
    }

    const validas = new Map<string, { tipo: "video" | "perfil"; url: string }>();
    const invalidos: string[] = [];
    for (const c of crudas) {
      const e = clasificarEntrada(c);
      if (e) validas.set(e.url, e);
      else if (c.trim()) invalidos.push(c.trim().slice(0, 80));
    }
    if (!validas.size) {
      return NextResponse.json(
        { error: "Ningún enlace válido. Usa enlaces de TikTok (tiktok.com/@usuario/video/…, vm.tiktok.com/…), de Instagram (instagram.com/reel/…, /p/…) o @usuario de TikTok.", invalidos },
        { status: 400 }
      );
    }

    // No repetir lo que ya está en cola / importado
    const urls = [...validas.keys()];
    const { data: previas } = await supabaseAdmin
      .from("importaciones")
      .select("url, tipo, estado")
      .eq("propietario_fb_id", sesion.sub)
      .in("url", urls);
    const omitidos: string[] = [];
    for (const p of previas || []) {
      const bloquea = p.tipo === "video" ? ["pendiente", "procesando", "listo", "usado"] : ["pendiente", "procesando"];
      if (bloquea.includes(p.estado) && validas.delete(p.url)) omitidos.push(p.url);
    }
    if (!validas.size) return NextResponse.json({ creados: 0, omitidos, invalidos, despacho: null });

    const { count } = await supabaseAdmin
      .from("importaciones")
      .select("id", { count: "exact", head: true })
      .eq("propietario_fb_id", sesion.sub)
      .in("estado", ["pendiente", "procesando"]);
    if ((count ?? 0) + validas.size > MAX_ACTIVAS) {
      return NextResponse.json({ error: `Tienes demasiadas importaciones en cola (máx. ${MAX_ACTIVAS}). Espera a que terminen.` }, { status: 429 });
    }

    const { data: creadas, error } = await supabaseAdmin
      .from("importaciones")
      .insert([...validas.values()].map((e) => ({ propietario_fb_id: sesion.sub, tipo: e.tipo, url: e.url })))
      .select("id");
    if (error) throw error;

    const despacho = await despacharWorker();
    return NextResponse.json({ creados: creadas?.length ?? 0, omitidos, invalidos, despacho });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al importar" }, { status: 500 });
  }
}

