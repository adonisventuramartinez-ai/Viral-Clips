import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const MAX_MB = 45;
const EXT = ["mp4", "m4v", "mov", "webm", "mkv", "avi"];

/**
 * Da una URL firmada para subir un video directo a Supabase Storage (bucket 'uploads').
 * El navegador hace PUT a signedUrl y después manda solo `upload_path` a /api/jobs.
 * Así un video de 200 MB no pasa por la función de Vercel (límite ~4.5 MB por request).
 */
export async function POST(req: Request) {
  const { name, size, type } = await req.json().catch(() => ({})) as { name?: unknown; size?: unknown; type?: unknown };

  const filename = typeof name === "string" ? name : "";
  const ext = (filename.split(".").pop() || "").toLowerCase();
  if (!EXT.includes(ext)) {
    return NextResponse.json({ error: "Formato no admitido. Usa MP4, MOV, M4V, WEBM, MKV o AVI." }, { status: 400 });
  }
  const bytes = Number(size) || 0;
  if (bytes <= 0 || bytes > MAX_MB * 1024 * 1024) {
    return NextResponse.json({ error: `El video debe pesar entre 1 KB y ${MAX_MB} MB. Comprime el archivo o usa un link .mp4.` }, { status: 413 });
  }
  if (typeof type === "string" && type && !type.startsWith("video/")) {
    return NextResponse.json({ error: "El archivo debe ser un video." }, { status: 400 });
  }

  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true, message: "Modo demo: conecta Supabase para subir de verdad." });
  const path = `incoming/${randomUUID()}.${ext}`;
  const { data, error } = await db.storage.from("uploads").createSignedUploadUrl(path);
  if (error || !data) {
    return NextResponse.json({ error: error?.message || "No se pudo crear la URL de subida." }, { status: 500 });
  }
  return NextResponse.json({
    ok: true,
    path,
    signedUrl: data.signedUrl,
    token: data.token,
    maxBytes: MAX_MB * 1024 * 1024,
  });
}
