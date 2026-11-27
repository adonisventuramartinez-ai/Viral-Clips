import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin, BUCKET } from "@/lib/db";
import { publicarEnPagina } from "@/lib/fbServer";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

// "Publicar ahora" con Reel: usa la API OFICIAL de Reels (video_reels, 3 pasos) igual que el cron.
// El navegador sube el archivo a Supabase Storage (sin pasar por Vercel) y aquí solo se le
// pasa a Facebook una URL firmada. Antes se usaba /videos?is_reel=true, que publica un video
// normal sin distribución de Reels.
export async function POST(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  try {
    const { paginaId, token, path, titulo, mensaje } = await req.json();
    if (!/^\d+$/.test(String(paginaId)) || typeof token !== "string" || token.length < 20) {
      return NextResponse.json({ ok: false, error: "Datos de página inválidos" }, { status: 400 });
    }
    if (typeof path !== "string" || !path.startsWith(`${sesion.sub}/`) || path.includes("..")) {
      return NextResponse.json({ ok: false, error: "Archivo no válido" }, { status: 400 });
    }
    const { data: firmada, error } = await supabaseAdmin.storage.from(BUCKET).createSignedUrl(path, 3600);
    if (error || !firmada?.signedUrl) {
      return NextResponse.json({ ok: false, error: `No se pudo firmar el archivo: ${error?.message}` }, { status: 500 });
    }
    const r = await publicarEnPagina({
      paginaId: String(paginaId),
      token,
      tipo: "reel",
      urlArchivo: firmada.signedUrl,
      titulo: titulo || null,
      mensaje: mensaje || null,
    });
    return NextResponse.json(r);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || "Error al publicar el reel" }, { status: 500 });
  }
}

