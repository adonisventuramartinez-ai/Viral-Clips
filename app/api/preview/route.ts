import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const LAYOUTS = ["crop", "casa", "split", "split_eq", "split_game", "blur", "duo"];
const TYPES = ["auto", "reality", "podcast", "entrevista", "juego", "gta", "gta6", "gta_rp", "directo"];
const PREVIEW_TITLE = "__preview__";

/**
 * Vista previa de cómo quedará un clip, SIN crear los clips.
 * POST { url, t, layout, custom_crop, content_type, game, brand_template, hook } -> crea una fuente temporal ("done", para que no salga
 *   en la cola) y un trabajo con prioridad alta. Devuelve { id }.
 * GET ?id=... -> { status: "working" | "ready" | "error", url?, error? }. Al terminar (bien o mal) borra la fuente temporal.
 */
export async function POST(req: Request) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ error: "Conecta Supabase para ver la vista previa" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const url = typeof b.url === "string" ? b.url.trim() : "";
  if (!/^https?:\/\/\S+$/i.test(url) || url.length > 500) return NextResponse.json({ error: "Pega primero un link válido (https://…)" }, { status: 400 });

  const { data: busy } = await db.from("sources").select("id").eq("title", PREVIEW_TITLE).gte("created_at", new Date(Date.now() - 3 * 60 * 1000).toISOString()).limit(1);
  if (busy && busy.length) return NextResponse.json({ error: "Ya hay una vista previa en camino. Espera a que termine." }, { status: 409 });

  const layout = LAYOUTS.includes(b.layout) ? b.layout : "crop";
  const content_type = TYPES.includes(b.content_type) ? b.content_type : "auto";
  const game = typeof b.game === "string" && b.game.trim() ? b.game.trim().slice(0, 60) : null;
  const brand_template = typeof b.brand_template === "string" && /^[a-z0-9-]{1,40}$/.test(b.brand_template) ? b.brand_template : null;
  const hook = typeof b.hook === "string" ? b.hook.trim().slice(0, 70) : "";
  const t = typeof b.t === "string" || typeof b.t === "number" ? String(b.t).slice(0, 12) : "";

  const row = { kind: "vod_url", url, title: PREVIEW_TITLE, status: "done", layout, custom_crop: b.custom_crop ?? null };
  let ins = await db.from("sources").insert({ ...row, options: { content_type, game, brand_template } }).select("id").single();
  if (ins.error && /options/i.test(ins.error.message)) ins = await db.from("sources").insert(row).select("id").single();
  if (ins.error) return NextResponse.json({ error: ins.error.message }, { status: 500 });
  const id = ins.data.id as string;

  const job = { source_id: id, type: "clip", payload: { preview: true, t, hook, content_type, game, brand_template, layout }, priority: 8 };
  let jr = await db.from("jobs").insert(job);
  if (jr.error && /priority/i.test(jr.error.message)) { const { priority: _p, ...rest } = job; jr = await db.from("jobs").insert(rest); }
  if (jr.error) { await db.from("sources").delete().eq("id", id); return NextResponse.json({ error: jr.error.message }, { status: 500 }); }
  return NextResponse.json({ ok: true, id });
}

export async function GET(req: Request) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ status: "error", error: "Supabase no está conectado" }, { status: 503 });
  const id = new URL(req.url).searchParams.get("id") ?? "";
  if (!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({ status: "error", error: "Id no válido" }, { status: 400 });

  const { data: src } = await db.from("sources").select("id,title,progress,created_at").eq("id", id).maybeSingle();
  if (!src || src.title !== PREVIEW_TITLE) return NextResponse.json({ status: "error", error: "Esa vista previa ya no existe" }, { status: 404 });
  const p = src.progress ?? {};

  if (p.preview) {
    const { data } = await db.storage.from("uploads").createSignedUrl(p.preview, 600);
    await db.from("sources").delete().eq("id", id);
    return NextResponse.json({ status: "ready", url: data?.signedUrl ?? null });
  }
  if (p.preview_error) {
    await db.from("sources").delete().eq("id", id);
    return NextResponse.json({ status: "error", error: p.preview_error });
  }
  const age = Date.now() - new Date(src.created_at).getTime();
  if (age > 4 * 60 * 1000) {   // el worker no contestó: seguramente está apagado u ocupado con otro video
    await db.from("jobs").update({ status: "done" }).eq("source_id", id).eq("status", "queued");
    await db.from("sources").delete().eq("id", id);
    return NextResponse.json({ status: "error", error: "El worker no respondió. ¿Está encendido o muy ocupado? Inténtalo otra vez." });
  }
  return NextResponse.json({ status: "working" });
}
