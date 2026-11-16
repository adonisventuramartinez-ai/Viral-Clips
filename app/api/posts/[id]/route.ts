import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

/** Acciones sobre una publicación: cancelar, reintentar (a los 2 minutos) o cambiar la hora. */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const { data: cur } = await db.from("posts").select("status").eq("id", params.id).maybeSingle();
  if (!cur) return NextResponse.json({ error: "No existe" }, { status: 404 });
  if (cur.status === "published" || cur.status === "publishing")
    return NextResponse.json({ error: "Ya está publicado o publicándose" }, { status: 409 });
  const upd: Record<string, unknown> = {};
  if (b.action === "cancel") { upd.status = "cancelled"; }
  else if (b.action === "retry") { upd.status = "queued"; upd.error = null; upd.scheduled_at = new Date(Date.now() + 2 * 60_000).toISOString(); }
  else if (b.scheduled_at) {
    const t = Date.parse(String(b.scheduled_at));
    if (!Number.isFinite(t) || t < Date.now() + 60_000 || t > Date.now() + 60 * 86_400_000)
      return NextResponse.json({ error: "Elige una fecha entre dentro de 1 minuto y 60 días" }, { status: 400 });
    upd.scheduled_at = new Date(t).toISOString(); upd.status = "queued"; upd.error = null;
  } else return NextResponse.json({ error: "Nada que cambiar" }, { status: 400 });
  const { error } = await db.from("posts").update(upd).eq("id", params.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
