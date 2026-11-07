import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Diagnóstico: abre /api/health (ya logueado) y te dice qué falta. No muestra ninguna llave.
export async function GET() {
  const env = {
    NEXT_PUBLIC_SUPABASE_URL: !!process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_ROLE_KEY: !!process.env.SUPABASE_SERVICE_ROLE_KEY,
    APP_PASSWORD: !!process.env.APP_PASSWORD,
  };
  const db = serverClient();
  if (!db) {
    return NextResponse.json({ ok: false, env, problema: "Faltan variables de Supabase en Vercel (revisa los false de 'env') y haz Redeploy." });
  }

  const tablas: Record<string, string> = {};
  for (const t of ["sources", "clips", "jobs", "rejected_moments", "transcript_segments"]) {
    const { error } = await db.from(t).select("*", { head: true, count: "exact" }).limit(1);
    tablas[t] = error ? `ERROR: ${error.message}` : "ok";
  }

  const { data: buckets, error: bErr } = await db.storage.listBuckets();
  const bucketClips = bErr ? `ERROR: ${bErr.message}` : buckets?.some((b) => b.name === "clips") ? "ok" : "NO EXISTE el bucket 'clips'";

  const { data: jobs } = await db.from("jobs").select("status");
  const jobsPorEstado: Record<string, number> = {};
  (jobs ?? []).forEach((j) => (jobsPorEstado[j.status] = (jobsPorEstado[j.status] ?? 0) + 1));

  const { data: errores } = await db.from("sources").select("url,error,created_at").eq("status", "error").order("created_at", { ascending: false }).limit(3);

  const ok = Object.values(tablas).every((v) => v === "ok") && bucketClips === "ok";
  return NextResponse.json({ ok, env, tablas, bucketClips, jobsPorEstado, ultimosErrores: errores ?? [] });
}
