import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { encriptar } from "@/lib/crypto";
import { GRAPH_BASE } from "@/lib/graph";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";

// POST: guarda una cuenta nueva (token de usuario obtenido por OAuth en el
// navegador). Se valida contra Facebook, se encripta y queda ligada al dueño.
export async function POST(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  try {
    const { nombre, userToken } = await req.json();
    if (!nombre || !userToken || typeof nombre !== "string" || nombre.length > 80) {
      return NextResponse.json({ error: "Faltan datos (nombre, userToken)" }, { status: 400 });
    }

    const check = await fetch(`${GRAPH_BASE}/me?access_token=${encodeURIComponent(userToken)}`);
    const checkData = await check.json();
    if (checkData.error) {
      return NextResponse.json({ error: "Token de Facebook inválido: " + checkData.error.message }, { status: 400 });
    }

    const { data, error } = await supabaseAdmin
      .from("cuentas_fb")
      .insert({
        nombre: nombre.trim(),
        token_encriptado: encriptar(userToken),
        propietario_fb_id: sesion.sub,
      })
      .select("id, nombre, creado_en")
      .single();

    if (error) throw error;
    return NextResponse.json({ cuenta: data });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al guardar la cuenta" }, { status: 500 });
  }
}

// GET: cuentas del usuario (nunca expone tokens)
export async function GET(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  const consulta = (columnas: string) =>
    supabaseAdmin
      .from("cuentas_fb")
      .select(columnas)
      .eq("propietario_fb_id", sesion.sub)
      .order("creado_en", { ascending: false });

  // token_invalido_en lo crea la migración 005: si aún no existe, se lista igual sin ese dato
  let { data, error } = await consulta("id, nombre, creado_en, token_invalido_en");
  if (error) ({ data, error } = await consulta("id, nombre, creado_en"));

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ cuentas: data });
}

