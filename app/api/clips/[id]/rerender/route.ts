import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

/** "1:23", "1:02:03" o "83" -> segundos (NaN si no vale) */
function toSec(v: unknown): number {
  const p = String(v ?? "").trim().split(":").map(Number);
  if (!p.length || p.length > 3 || p.some((n) => !Number.isFinite(n) || n < 0)) return NaN;
  return p.reduce((a, n) => a * 60 + n, 0);
}

/** Pide al worker volver a hacer un clip con otro inicio/fin y/u otro encuadre. */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const start = toSec(b.start), end = toSec(b.end);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return NextResponse.json({ error: "Escribe el inicio y el fin como 1:23" }, { status: 400 });
  if (end - start < 5 || end - start > 180) return NextResponse.json({ error: "El clip debe durar entre 5 y 180 segundos" }, { status: 400 });
  const layout = ["crop", "split", "blur", "duo"].includes(b.layout) ? b.layout : null;
  const quality = ["720p", "1080p", "1440p", "2160p"].includes(b.quality) ? b.quality : "1080p";

  const { data: clip } = await db.from("clips").select("id,source_id").eq("id", params.id).maybeSingle();
  if (!clip) return NextResponse.json({ error: "Clip no encontrado" }, { status: 404 });
  const { data: src } = await db.from("sources").select("kind,url").eq("id", clip.source_id).maybeSingle();
  if (!src || src.kind === "live" || !src.url) return NextResponse.json({ error: "Los clips de directos no se pueden ajustar (el directo ya no existe)" }, { status: 400 });

  const { data: busy } = await db.from("jobs").select("id").eq("type", "clip").in("status", ["queued", "running"]).contains("payload", { clip_id: params.id }).limit(1);
  if (busy && busy.length) return NextResponse.json({ error: "Este clip ya se está ajustando" }, { status: 409 });

  const { error } = await db.from("jobs").insert({ source_id: clip.source_id, type: "clip", payload: { clip_id: params.id, start, end, layout, quality } });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
