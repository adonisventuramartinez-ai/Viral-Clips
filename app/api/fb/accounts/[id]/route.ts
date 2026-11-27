import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";
import { encriptar } from "@/lib/crypto";
import { GRAPH_BASE } from "@/lib/graph";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// PATCH { userToken } → RECONECTA la cuenta con un token nuevo SIN borrarla: se guarda el
// token, se limpia el aviso de "token vencido" y se refrescan los tokens de página de todas
// sus publicaciones pendientes o con error (cada post guarda su propia copia).
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  const id = Number(idParam);
  if (!Number.isInteger(id) || id <= 0) return NextResponse.json({ error: "ID inválido" }, { status: 400 });

  try {
    const { userToken } = await req.json().catch(() => ({}));
    if (!userToken || typeof userToken !== "string") {
      return NextResponse.json({ error: "Falta userToken" }, { status: 400 });
    }

    const { data: cuenta } = await supabaseAdmin
      .from("cuentas_fb")
      .select("id")
      .eq("id", id)
      .eq("propietario_fb_id", sesion.sub)
      .maybeSingle();
    if (!cuenta) return NextResponse.json({ error: "Cuenta no encontrada" }, { status: 404 });

    const r = await fetch(
      `${GRAPH_BASE}/me/accounts?access_token=${encodeURIComponent(userToken)}&fields=id,name,access_token&limit=200`,
      { signal: AbortSignal.timeout(15_000) }
    );
    const d = await r.json();
    if (d.error) return NextResponse.json({ error: "Token de Facebook inválido: " + d.error.message }, { status: 400 });
    const tokensPagina = new Map<string, string>((d.data || []).map((p: any) => [String(p.id), String(p.access_token)]));

    const { error: errGuardar } = await supabaseAdmin
      .from("cuentas_fb")
      .update({ token_encriptado: encriptar(userToken), token_invalido_en: null })
      .eq("id", id)
      .eq("propietario_fb_id", sesion.sub);
    if (errGuardar) throw errGuardar;

    const { data: posts } = await supabaseAdmin
      .from("posts_programados")
      .select("id, paginas")
      .eq("cuenta_id", id)
      .eq("propietario_fb_id", sesion.sub)
      .in("estado", ["pendiente", "error"])
      .limit(1000);

    let refrescados = 0;
    for (let i = 0; i < (posts || []).length; i += 10) {
      await Promise.all(
        (posts || []).slice(i, i + 10).map(async (post: any) => {
          let cambio = false;
          const paginas = (post.paginas || []).map((p: any) => {
            const nuevo = tokensPagina.get(String(p.id));
            if (!nuevo) return p;
            cambio = true;
            return { ...p, access_token_encriptado: encriptar(nuevo) };
          });
          if (!cambio) return;
          const { error } = await supabaseAdmin.from("posts_programados").update({ paginas }).eq("id", post.id);
          if (!error) refrescados++;
        })
      );
    }
    return NextResponse.json({ ok: true, publicaciones_actualizadas: refrescados });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al reconectar la cuenta" }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  const id = Number(idParam);
  if (!Number.isInteger(id)) return NextResponse.json({ error: "ID inválido" }, { status: 400 });

  // Al borrar la cuenta, sus publicaciones pendientes se cancelan (llevan el token
  // de las páginas guardado y, si no, seguirían publicando con una cuenta "borrada").
  await supabaseAdmin
    .from("posts_programados")
    .update({ estado: "cancelado" })
    .eq("cuenta_id", id)
    .eq("propietario_fb_id", sesion.sub)
    .in("estado", ["pendiente", "error"]);

  const { data, error } = await supabaseAdmin
    .from("cuentas_fb")
    .delete()
    .eq("id", id)
    .eq("propietario_fb_id", sesion.sub)
    .select("id");

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data?.length) return NextResponse.json({ error: "Cuenta no encontrada" }, { status: 404 });
  return NextResponse.json({ ok: true });
}
