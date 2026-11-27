import { NextRequest, NextResponse } from "next/server";
import { autorizadoWorker, tokenDePagina } from "@/lib/autopilot";
import { signClipPaths } from "@/lib/storage";
import { publicarEnPagina } from "@/lib/fbServer";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

// El worker llama aquí firmando el cuerpo con R2_SECRET_ACCESS_KEY (la misma llave de Tigris).
// La web busca el token fresco de la página en su Supabase, firma el clip y publica el Reel.
export async function POST(req: NextRequest) {
  const raw = await req.text();
  if (!autorizadoWorker(raw, req.headers.get("x-autopiloto"))) {
    return NextResponse.json({ ok: false, error: "No autorizado (falta la llave R2/Tigris en Vercel)" }, { status: 401 });
  }
  let b: any = {};
  try {
    b = raw ? JSON.parse(raw) : {};
  } catch {
    return NextResponse.json({ ok: false, error: "JSON inválido" }, { status: 400 });
  }
  const pageId = String(b.page_id ?? "");
  const path = String(b.storage_path ?? "");
  if (!/^\d{5,}$/.test(pageId)) return NextResponse.json({ ok: false, error: "Página no válida" }, { status: 400 });
  if (!/^[\w./-]+\.mp4$/i.test(path) || path.includes("..")) {
    return NextResponse.json({ ok: false, error: "Archivo no válido" }, { status: 400 });
  }
  const title = String(b.title ?? "").slice(0, 255);
  const message = String(b.message ?? "").slice(0, 5000);

  try {
    const t = await tokenDePagina(pageId);
    if (!t.token) return NextResponse.json({ ok: false, error: t.error || "Sin token para esa página" }, { status: 404 });

    const signed = await signClipPaths([path], 6 * 3600);
    const url = signed[0]?.signedUrl;
    if (!url) return NextResponse.json({ ok: false, error: "No pude firmar el clip (revisa /almacenamiento)" }, { status: 500 });

    const r = await publicarEnPagina({
      paginaId: pageId,
      token: t.token,
      tipo: "reel",
      urlArchivo: url,
      titulo: title || null,
      mensaje: message || null,
    });
    return NextResponse.json(r);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e).slice(0, 300) }, { status: 500 });
  }
}
