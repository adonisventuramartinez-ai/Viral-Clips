import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { desencriptar, encriptar } from "@/lib/crypto";
import { GRAPH_BASE } from "@/lib/graph";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";

const TIPOS = ["foto", "video", "reel"];
const RECURRENCIAS = ["ninguna", "diaria", "semanal"];

// POST: crea una publicación programada.
// El cliente NUNCA envía tokens: solo cuenta_id + ids de páginas. El servidor
// pide a Facebook el token fresco de cada página y lo guarda encriptado.
export async function POST(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  try {
    const b = await req.json();
    const { cuenta_id, paginas, tipo, titulo, mensaje, archivo_url, archivo_nombre, fecha_programada } = b;
    const recurrencia = b.recurrencia || "ninguna";

    // --- Validación
    if (!cuenta_id || !Array.isArray(paginas) || !paginas.length || !tipo || !archivo_url || !fecha_programada) {
      return NextResponse.json({ error: "Faltan datos obligatorios" }, { status: 400 });
    }
    if (!TIPOS.includes(tipo)) return NextResponse.json({ error: "Tipo inválido" }, { status: 400 });
    if (!RECURRENCIAS.includes(recurrencia)) return NextResponse.json({ error: "Recurrencia inválida" }, { status: 400 });
    if (paginas.length > 25 || paginas.some((p: any) => !/^\d+$/.test(String(p?.id)))) {
      return NextResponse.json({ error: "Lista de páginas inválida" }, { status: 400 });
    }
    const fecha = new Date(fecha_programada);
    if (isNaN(fecha.getTime()) || fecha.getTime() <= Date.now()) {
      return NextResponse.json({ error: "La fecha debe ser válida y en el futuro" }, { status: 400 });
    }
    // El archivo tiene que estar en la carpeta del propio usuario
    if (typeof archivo_url !== "string" || !archivo_url.startsWith(`${sesion.sub}/`) || archivo_url.includes("..")) {
      return NextResponse.json({ error: "Archivo no válido" }, { status: 400 });
    }
    if ((titulo && String(titulo).length > 255) || (mensaje && String(mensaje).length > 10000)) {
      return NextResponse.json({ error: "Título o mensaje demasiado largo" }, { status: 400 });
    }

    // --- La cuenta debe ser del usuario
    const { data: cuenta } = await supabaseAdmin
      .from("cuentas_fb")
      .select("token_encriptado")
      .eq("id", cuenta_id)
      .eq("propietario_fb_id", sesion.sub)
      .single();
    if (!cuenta) return NextResponse.json({ error: "Cuenta no encontrada" }, { status: 404 });

    const userToken = desencriptar(cuenta.token_encriptado);
    const paginasRes = await fetch(
      `${GRAPH_BASE}/me/accounts?access_token=${encodeURIComponent(userToken)}&fields=id,name,access_token&limit=200`
    );
    const paginasData = await paginasRes.json();
    if (paginasData.error) {
      return NextResponse.json(
        { error: "No se pudo obtener el token de las páginas: " + paginasData.error.message },
        { status: 400 }
      );
    }

    const idsPedidos = new Set(paginas.map((p: any) => String(p.id)));
    const paginasConToken = (paginasData.data || [])
      .filter((p: any) => idsPedidos.has(p.id))
      .map((p: any) => ({ id: p.id, name: p.name, access_token_encriptado: encriptar(p.access_token) }));

    if (paginasConToken.length === 0) {
      return NextResponse.json({ error: "Ninguna de las páginas seleccionadas pertenece a esta cuenta" }, { status: 400 });
    }

    const { data, error } = await supabaseAdmin
      .from("posts_programados")
      .insert({
        cuenta_id,
        propietario_fb_id: sesion.sub,
        paginas: paginasConToken,
        tipo,
        titulo: titulo || null,
        mensaje: mensaje || null,
        archivo_url,
        archivo_nombre: archivo_nombre || null,
        fecha_programada: fecha.toISOString(),
        recurrencia,
        estado: "pendiente",
        resultados: {},
      })
      .select("id")
      .single();

    if (error) throw error;
    return NextResponse.json({ id: data.id });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al programar la publicación" }, { status: 500 });
  }
}

// GET: publicaciones del usuario (sin exponer tokens)
export async function GET(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  const { data, error } = await supabaseAdmin
    .from("posts_programados")
    .select(
      "id, cuenta_id, paginas, tipo, titulo, mensaje, archivo_nombre, fecha_programada, recurrencia, estado, intentos, resultados, ultimo_error, serie_id, creado_en"
    )
    .eq("propietario_fb_id", sesion.sub)
    .order("fecha_programada", { ascending: true })
    .limit(500);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const limpio = (data || []).map((post: any) => ({
    ...post,
    paginas: post.paginas.map((p: any) => ({ id: p.id, name: p.name })),
  }));
  return NextResponse.json({ posts: limpio });
}

