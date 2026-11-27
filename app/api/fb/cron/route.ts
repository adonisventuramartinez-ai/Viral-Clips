import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { supabaseAdmin, BUCKET, PostProgramado, ResultadoPagina } from "@/lib/db";
import { desencriptar } from "@/lib/crypto";
import { publicarEnPagina } from "@/lib/fbServer";
import { decidir, siguienteOcurrencia } from "@/lib/planificador";
import { limpiarStorage } from "@/lib/limpieza";
import { retrasoEscalonado, variarHashtags } from "@/lib/variacion";

// Sin esto Next.js puede cachear el GET como estático y el cron recibiría
// siempre la misma respuesta congelada.
export const dynamic = "force-dynamic";
export const revalidate = 0;
export const maxDuration = 60;

const PRESUPUESTO_MS = 40_000; // no se empieza ningún post nuevo pasado este tiempo (margen para terminar el último)
const POSTS_POR_EJECUCION = 12;
const CONCURRENCIA = 3; // posts que se publican a la vez
const MINUTOS_PARA_RESCATAR = 10; // un "publicando" más viejo que esto se considera atascado
const HORAS_ENTRE_LIMPIEZAS = 6;

function secretoValido(req: NextRequest): boolean {
  const esperado = (process.env.CRON_SECRET || "").trim();
  if (!esperado) return false; // sin CRON_SECRET configurado la ruta queda cerrada
  const recibido = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();
  const a = crypto.createHash("sha256").update(recibido).digest();
  const b = crypto.createHash("sha256").update(esperado).digest();
  return crypto.timingSafeEqual(a, b);
}

export async function GET(req: NextRequest) {
  if (!(process.env.CRON_SECRET || "").trim()) {
    return NextResponse.json({ error: "CRON_SECRET no está configurado en el servidor" }, { status: 500 });
  }
  if (!secretoValido(req)) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const inicio = Date.now();
  const ahoraISO = new Date(inicio).toISOString();
  const salida: any[] = [];

  try {
    // 1) Rescatar posts atascados en "publicando" (la función murió a mitad).
    //    El resultado de cada página ya se guardó al terminar, así que el reintento
    //    NO repite las páginas que sí salieron.
    const limite = new Date(inicio - MINUTOS_PARA_RESCATAR * 60_000).toISOString();
    const { data: rescatados } = await supabaseAdmin
      .from("posts_programados")
      .update({ estado: "pendiente", bloqueado_en: null })
      .eq("estado", "publicando")
      .lt("bloqueado_en", limite)
      .select("id");

    // 2) Buscar vencidos
    const { data: posts, error } = await supabaseAdmin
      .from("posts_programados")
      .select("id")
      .eq("estado", "pendiente")
      .lte("fecha_programada", ahoraISO)
      .order("fecha_programada", { ascending: true })
      .limit(POSTS_POR_EJECUCION);
    if (error) throw error;

    // 3) Procesar con un pequeño grupo de "trabajadores" en paralelo. Cada uno toma el
    //    siguiente post de la fila y lo RECLAMA de forma atómica; así un post lento
    //    (p. ej. un reel que tarda en procesarse) no bloquea a los demás.
    const fila = [...(posts || [])] as { id: number }[];
    const trabajador = async () => {
      while (fila.length && Date.now() - inicio < PRESUPUESTO_MS) {
        const candidato = fila.shift()!;
        // Reclamo atómico: solo UNA ejecución consigue pasar de pendiente → publicando
        const { data: reclamado } = await supabaseAdmin
          .from("posts_programados")
          .update({ estado: "publicando", bloqueado_en: new Date().toISOString() })
          .eq("id", candidato.id)
          .eq("estado", "pendiente")
          .select("*");
        if (!reclamado?.length) continue; // otra ejecución se lo llevó (o se canceló)
        salida.push(await procesar(reclamado[0] as PostProgramado));
      }
    };
    await Promise.all(Array.from({ length: CONCURRENCIA }, trabajador));

    // 4) Mantenimiento (solo si sobra tiempo): limpieza de Storage cada pocas horas
    const limpieza = await mantenimiento(inicio);

    // Latido: el panel lo usa para saber si el cron sigue corriendo (los errores se ignoran)
    await supabaseAdmin
      .from("cron_latido")
      .upsert({ id: 1, ultimo: new Date().toISOString(), procesados: salida.length })
      .then(() => {}, () => {});

    return NextResponse.json({
      ok: true,
      procesados: salida.length,
      rescatados: rescatados?.length ?? 0,
      pendientes_sin_atender: fila.length,
      limpieza,
      ms: Date.now() - inicio,
      resultados: salida,
    });
  } catch (err: any) {
    console.error("[cron] error general:", err);
    return NextResponse.json({ error: err.message || "Error interno" }, { status: 500 });
  }
}

async function mantenimiento(inicio: number) {
  if (process.env.LIMPIEZA_STORAGE === "off") return null;
  if (Date.now() - inicio > PRESUPUESTO_MS - 10_000) return null; // sin tiempo: queda para la próxima
  try {
    // La columna ultima_limpieza la crea la migración 005; si no existe, se omite sin romper nada
    const { data, error } = await supabaseAdmin.from("cron_latido").select("ultima_limpieza").eq("id", 1).maybeSingle();
    if (error) return null;
    const ultima = data?.ultima_limpieza ? new Date(data.ultima_limpieza).getTime() : 0;
    if (Date.now() - ultima < HORAS_ENTRE_LIMPIEZAS * 3600_000) return null;

    const r = await limpiarStorage();
    await supabaseAdmin
      .from("cron_latido")
      .upsert({ id: 1, ultima_limpieza: new Date().toISOString() })
      .then(() => {}, () => {});
    return r;
  } catch (e: any) {
    console.error("[cron] limpieza de Storage falló:", e?.message || e);
    return null;
  }
}

async function procesar(post: PostProgramado) {
  const resultados: Record<string, ResultadoPagina> = { ...(post.resultados || {}) };

  // Los guardados se encadenan para que lleguen en orden (si dos páginas terminan a la vez,
  // el último en escribir siempre trae el estado completo). También renueva "bloqueado_en":
  // un post que sigue trabajando no será "rescatado" por otra ejecución.
  let cola: Promise<unknown> = Promise.resolve();
  const guardarProgreso = () => {
    const copia = JSON.parse(JSON.stringify(resultados));
    cola = cola.then(() =>
      supabaseAdmin
        .from("posts_programados")
        .update({ resultados: copia, bloqueado_en: new Date().toISOString() })
        .eq("id", post.id)
        .then(
          ({ error }) => error && console.error(`[cron] no se pudo guardar el progreso del post ${post.id}:`, error.message),
          () => {}
        )
    );
    return cola;
  };

  try {
    // URL firmada para que Facebook descargue el archivo él mismo (6 h de vigencia)
    const { data: firmada, error: errFirma } = await supabaseAdmin.storage
      .from(BUCKET)
      .createSignedUrl(post.archivo_url, 6 * 3600);
    if (errFirma || !firmada?.signedUrl) throw new Error(`No se pudo firmar el archivo: ${errFirma?.message}`);

    // Solo las páginas que AÚN no salieron (así un reintento no duplica)
    const pendientes = post.paginas.filter((p) => !resultados[p.id]?.ok);

    await Promise.all(
      pendientes.map(async (pagina, indice) => {
        // Anti-duplicado: cada página sale unos segundos después de la anterior
        if (process.env.ESCALONAR !== "off") {
          const espera = retrasoEscalonado(indice, pendientes.length);
          if (espera > 0) await new Promise((r) => setTimeout(r, espera));
        }
        let token: string;
        try {
          token = desencriptar(pagina.access_token_encriptado);
        } catch {
          resultados[pagina.id] = {
            ok: false,
            error: "No se pudo desencriptar el token de la página (¿cambió ENCRYPTION_KEY?)",
            reintentable: false,
            en: new Date().toISOString(),
          };
          return;
        }
        const r = await publicarEnPagina({
          paginaId: pagina.id,
          token,
          tipo: post.tipo,
          urlArchivo: firmada.signedUrl,
          titulo: post.titulo,
          mensaje: process.env.VARIAR_TEXTO === "off" ? post.mensaje : variarHashtags(post.mensaje, pagina.id + ":" + post.id),
        });
        resultados[pagina.id] = { ...r, en: new Date().toISOString() };
        // Guardar YA: si la función muere ahora, esta página no se vuelve a publicar
        await guardarProgreso();
      })
    );
  } catch (e: any) {
    // Fallo antes de poder publicar en ninguna página (archivo borrado, etc.)
    for (const p of post.paginas) {
      if (!resultados[p.id]?.ok) {
        resultados[p.id] = { ok: false, error: e.message, reintentable: true, en: new Date().toISOString() };
      }
    }
  }
  await cola;

  // Token de Facebook vencido o revocado: se marca la cuenta para que el panel pida reconectar
  if (post.cuenta_id && Object.values(resultados).some((r) => !r.ok && r.codigo === 190)) {
    await supabaseAdmin
      .from("cuentas_fb")
      .update({ token_invalido_en: new Date().toISOString() })
      .eq("id", post.cuenta_id)
      .then(() => {}, () => {});
  }

  const ahora = Date.now();
  const decision = decidir(
    post.paginas.map((p) => p.id),
    resultados,
    post.intentos || 0,
    ahora
  );

  // Si la serie debe continuar, clonamos la siguiente ocurrencia cuando este post
  // llega a un estado final (completado o error): una falla no corta la serie.
  if (decision.estado === "completado" || decision.estado === "error") {
    await programarSiguiente(post, ahora);
  }

  const cambios: Record<string, unknown> = {
    estado: decision.estado,
    intentos: decision.intentos,
    resultados,
    ultimo_error: decision.ultimoError,
    bloqueado_en: null,
  };
  if (decision.proximaFecha) {
    cambios.fecha_programada = decision.proximaFecha;
    // El reintento corre la fecha (5/20/60 min). Se recuerda la fecha original para que la
    // serie diaria/semanal no se vaya desplazando con cada fallo.
    if (!post.fecha_original) cambios.fecha_original = post.fecha_programada;
  }

  let { error } = await supabaseAdmin.from("posts_programados").update(cambios).eq("id", post.id);
  if (error && "fecha_original" in cambios) {
    // Base de datos sin la migración 005: se guarda igual sin esa columna para no dejar el post atascado
    delete cambios.fecha_original;
    ({ error } = await supabaseAdmin.from("posts_programados").update(cambios).eq("id", post.id));
  }
  if (error) console.error(`[cron] no se pudo guardar el resultado del post ${post.id}:`, error);

  return {
    id: post.id,
    estado: decision.estado,
    intentos: decision.intentos,
    ok: Object.values(resultados).filter((r) => r.ok).length,
    total: post.paginas.length,
    error: decision.ultimoError,
  };
}

async function programarSiguiente(post: PostProgramado, ahoraMs: number) {
  const proxima = siguienteOcurrencia(post.fecha_original ?? post.fecha_programada, post.recurrencia, ahoraMs);
  if (!proxima) return;

  const serie = post.serie_id ?? post.id;
  if (!post.serie_id) {
    await supabaseAdmin.from("posts_programados").update({ serie_id: serie }).eq("id", post.id);
  }

  const { error } = await supabaseAdmin.from("posts_programados").insert({
    cuenta_id: post.cuenta_id,
    propietario_fb_id: post.propietario_fb_id,
    paginas: post.paginas,
    tipo: post.tipo,
    titulo: post.titulo,
    mensaje: post.mensaje,
    archivo_url: post.archivo_url,
    archivo_nombre: post.archivo_nombre,
    fecha_programada: proxima,
    recurrencia: post.recurrencia,
    estado: "pendiente",
    intentos: 0,
    resultados: {},
    serie_id: serie,
  });
  // 23505 = el índice único (serie_id, fecha_programada) evitó un duplicado: correcto
  if (error && error.code !== "23505") console.error(`[cron] no se pudo crear la siguiente ocurrencia de ${post.id}:`, error);
}

