import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { desencriptar } from "@/lib/crypto";
import { GRAPH_BASE } from "@/lib/graph";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";
import { diagnosticar, infoDePagina, metricasDePublicacion, type GraphFn } from "@/lib/insights";
import type { TipoContenido } from "@/lib/facebook";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const MAX_POSTS = 40; // publicaciones programadas más recientes que se revisan
const MAX_ITEMS = 160; // publicaciones individuales (post × página)
const CONCURRENCIA = 8;
const PRESUPUESTO_MS = 40_000;
const TTL_CACHE_MS = 10 * 60_000;

function graphCon(token: string): GraphFn {
  return async (ruta, params = {}) => {
    const qs = new URLSearchParams({ ...params, access_token: token });
    const r = await fetch(`${GRAPH_BASE}/${ruta}?${qs}`, { signal: AbortSignal.timeout(12_000) });
    const d = await r.json();
    if (d.error) throw d.error;
    return d;
  };
}

async function enParalelo<T>(lista: T[], n: number, fn: (x: T) => Promise<void>, hastaMs: number) {
  const cola = [...lista];
  await Promise.all(
    Array.from({ length: n }, async () => {
      while (cola.length && Date.now() < hastaMs) await fn(cola.shift()!);
    })
  );
}

interface Item {
  postFbId: string; paginaId: string; paginaNombre: string; token: string;
  tipo: TipoContenido; titulo: string | null; postProgramadoId: number; fecha: string;
}

export async function GET(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  const inicio = Date.now();
  const refrescar = new URL(req.url).searchParams.get("refrescar") === "1";

  try {
    const { data: posts, error } = await supabaseAdmin
      .from("posts_programados")
      .select("id, tipo, titulo, fecha_programada, paginas, resultados, estado")
      .eq("propietario_fb_id", sesion.sub)
      .in("estado", ["completado", "error"])
      .order("fecha_programada", { ascending: false })
      .limit(MAX_POSTS);
    if (error) throw error;

    const items: Item[] = [];
    for (const p of posts || []) {
      for (const pag of p.paginas || []) {
        const r = p.resultados?.[pag.id];
        if (!r?.ok || !r.id) continue;
        try {
          items.push({
            postFbId: String(r.id), paginaId: pag.id, paginaNombre: pag.name,
            token: desencriptar(pag.access_token_encriptado), tipo: p.tipo,
            titulo: p.titulo, postProgramadoId: p.id, fecha: r.en || p.fecha_programada,
          });
        } catch { /* token no desencriptable: se omite */ }
      }
    }
    const recortados = items.slice(0, MAX_ITEMS);

    // Caché en Supabase (si la tabla aún no existe, se ignora sin romper nada)
    const cache = new Map<string, any>();
    let tablaOk = true;
    {
      const { data, error: e } = await supabaseAdmin
        .from("metricas_posts").select("*").eq("propietario_fb_id", sesion.sub);
      if (e) tablaOk = false;
      else for (const f of data || []) cache.set(f.post_fb_id, f);
    }

    const filas = new Map<string, any>();
    const porLeer: Item[] = [];
    for (const it of recortados) {
      const c = cache.get(it.postFbId);
      const fresco = c && Date.now() - new Date(c.actualizado_en).getTime() < TTL_CACHE_MS;
      if (c && fresco && !refrescar) filas.set(it.postFbId, c);
      else porLeer.push(it);
    }

    const leidos = new Set<string>();
    await enParalelo(porLeer, CONCURRENCIA, async (it) => {
      const m = await metricasDePublicacion(graphCon(it.token), it.postFbId, it.tipo);
      leidos.add(it.postFbId);
      filas.set(it.postFbId, {
        propietario_fb_id: sesion.sub, post_fb_id: it.postFbId, pagina_id: it.paginaId,
        pagina_nombre: it.paginaNombre, post_programado_id: it.postProgramadoId, tipo: it.tipo,
        titulo: it.titulo, publicado_en: m.publicadoEn || it.fecha, vistas: m.vistas, alcance: m.alcance,
        reacciones: m.reacciones, comentarios: m.comentarios, compartidos: m.compartidos,
        permalink: m.permalink, fuente: m.fuente, error: m.error, actualizado_en: new Date().toISOString(),
      });
    }, inicio + PRESUPUESTO_MS);

    // Los que no alcanzaron por tiempo se sirven desde caché vieja si existe
    for (const it of porLeer) if (!filas.has(it.postFbId) && cache.has(it.postFbId)) filas.set(it.postFbId, cache.get(it.postFbId));

    if (tablaOk && leidos.size) {
      const nuevos = [...leidos].map((id) => filas.get(id));
      await supabaseAdmin.from("metricas_posts").upsert(nuevos, { onConflict: "propietario_fb_id,post_fb_id" }).then(() => {}, () => {});
    }

    // Resumen por página (seguidores + vistas 28 días)
    const paginasUnicas = new Map<string, Item>();
    for (const it of recortados) if (!paginasUnicas.has(it.paginaId)) paginasUnicas.set(it.paginaId, it);
    const paginas: { id: string; nombre: string; seguidores: number | null; vistas28: number | null; error: string | null }[] = [];
    await enParalelo([...paginasUnicas.values()], CONCURRENCIA, async (it) => {
      const i = await infoDePagina(graphCon(it.token), it.paginaId);
      paginas.push({ id: it.paginaId, nombre: it.paginaNombre, ...i });
    }, inicio + PRESUPUESTO_MS + 10_000);

    const lista = recortados
      .map((it) => filas.get(it.postFbId))
      .filter(Boolean)
      .map((f) => ({
        id: f.post_fb_id, paginaId: f.pagina_id, pagina: f.pagina_nombre, tipo: f.tipo, titulo: f.titulo,
        fecha: f.publicado_en, vistas: f.vistas, alcance: f.alcance, reacciones: f.reacciones,
        comentarios: f.comentarios, compartidos: f.compartidos, permalink: f.permalink, error: f.error,
      }));

    const hace24h = Date.now() - 24 * 3600_000;
    const maduras = lista.filter((f) => f.fecha && new Date(f.fecha).getTime() < hace24h);
    const seguidoresMax = paginas.length && paginas.every((p) => p.seguidores !== null)
      ? Math.max(...paginas.map((p) => p.seguidores as number)) : null;
    const avisos = diagnosticar(maduras, seguidoresMax);
    if (!tablaOk) avisos.push("Opcional: ejecuta la migración 007_metricas_posts.sql en Supabase para guardar historial y acelerar esta pantalla.");
    if (!items.length) avisos.push("Aún no hay publicaciones programadas completadas. Las de “Publicar ahora” no guardan su id en el servidor: usa Programar o Lote para ver métricas aquí.");

    return NextResponse.json({
      items: lista,
      paginas: paginas.sort((a, b) => a.nombre.localeCompare(b.nombre)),
      avisos,
      totales: {
        vistas: lista.reduce((a, f) => a + (f.vistas || 0), 0),
        alcance: lista.reduce((a, f) => a + (f.alcance || 0), 0),
        reacciones: lista.reduce((a, f) => a + (f.reacciones || 0), 0),
        comentarios: lista.reduce((a, f) => a + (f.comentarios || 0), 0),
      },
      actualizado: new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al leer las métricas" }, { status: 500 });
  }
}

