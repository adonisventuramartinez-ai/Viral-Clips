import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";

// Resumen para el panel: contadores, próximas publicaciones y salud del cron.
export async function GET(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  const ahora = Date.now();
  const dueno = sesion.sub;
  const contar = () =>
    supabaseAdmin.from("posts_programados").select("id", { count: "exact", head: true }).eq("propietario_fb_id", dueno);

  const [pend, atras, hechos, errs, prox, latido] = await Promise.all([
    contar().eq("estado", "pendiente"),
    contar().eq("estado", "pendiente").lt("fecha_programada", new Date(ahora - 3 * 60_000).toISOString()),
    contar().eq("estado", "completado").gte("fecha_programada", new Date(ahora - 24 * 3600_000).toISOString()),
    contar().eq("estado", "error"),
    supabaseAdmin
      .from("posts_programados")
      .select("id, tipo, titulo, archivo_nombre, fecha_programada, paginas")
      .eq("propietario_fb_id", dueno)
      .eq("estado", "pendiente")
      .order("fecha_programada", { ascending: true })
      .limit(5),
    supabaseAdmin.from("cron_latido").select("ultimo, procesados").eq("id", 1).maybeSingle(),
  ]);

  let cron: { estado: "ok" | "lento" | "caido" | "sin_datos"; ultimo: string | null; segundos: number | null } = {
    estado: "sin_datos",
    ultimo: null,
    segundos: null,
  };
  if (!latido.error && latido.data?.ultimo) {
    const seg = Math.round((ahora - new Date(latido.data.ultimo).getTime()) / 1000);
    cron = { estado: seg <= 150 ? "ok" : seg <= 600 ? "lento" : "caido", ultimo: latido.data.ultimo, segundos: seg };
  }

  return NextResponse.json({
    pendientes: pend.count ?? 0,
    atrasadas: atras.count ?? 0,
    completadas24h: hechos.count ?? 0,
    conError: errs.count ?? 0,
    proximas: (prox.data || []).map((p: any) => ({ ...p, paginas: (p.paginas || []).map((x: any) => x.name) })),
    cron,
  });
}

