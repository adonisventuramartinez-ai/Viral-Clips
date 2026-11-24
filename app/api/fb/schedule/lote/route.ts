import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { desencriptar, encriptar } from "@/lib/crypto";
import { GRAPH_BASE, appUrl } from "@/lib/graph";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const TIPOS = ["foto", "video", "reel"];
const MAX_LOTE = 60;

// POST: crea VARIAS publicaciones programadas de una sola vez (un archivo = un post).
// Pide el token de las páginas a Facebook una sola vez para todo el lote.
export async function POST(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  try {
    const { cuenta_id, paginas, tipo, items, ahora: publicarYa } = await req.json();
    const modoAhora = publicarYa === true && Array.isArray(items) && items.length === 1;

    if (!cuenta_id || !Array.isArray(paginas) || !paginas.length || !TIPOS.includes(tipo) || !Array.isArray(items)) {
      return NextResponse.json({ error: "Faltan datos obligatorios" }, { status: 400 });
    }
    if (items.length === 0 || items.length > MAX_LOTE) {
      return NextResponse.json({ error: `El lote debe tener entre 1 y ${MAX_LOTE} publicaciones` }, { status: 400 });
    }
    if (paginas.length > 25 || paginas.some((p: any) => !/^\d+$/.test(String(p?.id)))) {
      return NextResponse.json({ error: "Lista de páginas inválida" }, { status: 400 });
    }

    const ahora = Date.now();
    const filas: any[] = [];
    for (const it of items) {
      const fecha = modoAhora ? new Date(ahora - 1000) : new Date(it?.fecha_programada);
      if (isNaN(fecha.getTime()) || (!modoAhora && fecha.getTime() <= ahora)) {
        return NextResponse.json({ error: `Fecha inválida o pasada en "${it?.archivo_nombre || "un elemento"}"` }, { status: 400 });
      }
      const ruta = it?.archivo_url;
      if (typeof ruta !== "string" || !ruta.startsWith(`${sesion.sub}/`) || ruta.includes("..")) {
        return NextResponse.json({ error: "Archivo no válido" }, { status: 400 });
      }
      if ((it.titulo && String(it.titulo).length > 255) || (it.mensaje && String(it.mensaje).length > 10000)) {
        return NextResponse.json({ error: "Título o mensaje demasiado largo" }, { status: 400 });
      }
      filas.push({ importacion_id: Number.isInteger(it.importacion_id) ? it.importacion_id : null, ruta, fecha, titulo: it.titulo || null, mensaje: it.mensaje || null, nombre: it.archivo_nombre || null });
    }

    const { data: cuenta } = await supabaseAdmin
      .from("cuentas_fb")
      .select("token_encriptado")
      .eq("id", cuenta_id)
      .eq("propietario_fb_id", sesion.sub)
      .single();
    if (!cuenta) return NextResponse.json({ error: "Cuenta no encontrada" }, { status: 404 });

    const userToken = desencriptar(cuenta.token_encriptado);
    const r = await fetch(`${GRAPH_BASE}/me/accounts?access_token=${encodeURIComponent(userToken)}&fields=id,name,access_token&limit=200`);
    const d = await r.json();
    if (d.error) {
      return NextResponse.json({ error: "No se pudo obtener el token de las páginas: " + d.error.message }, { status: 400 });
    }
    const pedidos = new Set(paginas.map((p: any) => String(p.id)));
    const paginasConToken = (d.data || [])
      .filter((p: any) => pedidos.has(p.id))
      .map((p: any) => ({ id: p.id, name: p.name, access_token_encriptado: encriptar(p.access_token) }));
    if (!paginasConToken.length) {
      return NextResponse.json({ error: "Ninguna de las páginas seleccionadas pertenece a esta cuenta" }, { status: 400 });
    }

    const { data, error } = await supabaseAdmin
      .from("posts_programados")
      .insert(
        filas.map((f) => ({
          cuenta_id,
          propietario_fb_id: sesion.sub,
          paginas: paginasConToken,
          tipo,
          titulo: f.titulo,
          mensaje: f.mensaje,
          archivo_url: f.ruta,
          archivo_nombre: f.nombre,
          fecha_programada: f.fecha.toISOString(),
          recurrencia: "ninguna",
          estado: "pendiente",
          resultados: {},
        }))
      )
      .select("id");
    if (error) throw error;

    // Los videos importados de TikTok que se acaban de programar pasan a "usado"
    const usados = filas.map((f) => f.importacion_id).filter((x): x is number => x !== null);
    if (usados.length) {
      await supabaseAdmin
        .from("importaciones")
        .update({ estado: "usado" })
        .in("id", usados)
        .eq("propietario_fb_id", sesion.sub)
        .eq("estado", "listo")
        .then(() => {}, () => {});
    }

    // "Publicar ahora": se dispara el cron desde el servidor para que salga ya, sin esperar al cron externo.
    let publicacion: { ok: boolean; error?: string } | undefined;
    if (modoAhora) {
      const secreto = (process.env.CRON_SECRET || "").trim();
      if (!secreto) {
        publicacion = { ok: false, error: "Falta CRON_SECRET en Vercel: el post quedó en cola y saldrá cuando corra el cron." };
      } else {
        try {
          const base = appUrl(new URL(req.url).origin);
          const rc = await fetch(`${base}/api/cron`, { headers: { Authorization: `Bearer ${secreto}` }, signal: AbortSignal.timeout(50_000), cache: "no-store" });
          publicacion = rc.ok ? { ok: true } : { ok: false, error: `El cron respondió ${rc.status}` };
        } catch (e: any) {
          publicacion = { ok: false, error: `No se pudo disparar el cron: ${e?.message || e}` };
        }
      }
    }

    return NextResponse.json({ creados: data?.length ?? 0, ids: (data || []).map((d: any) => d.id), publicacion });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al programar el lote" }, { status: 500 });
  }
}

