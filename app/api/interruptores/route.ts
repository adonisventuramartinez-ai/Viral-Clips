import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Botones de la web que mandan sobre worker/.env: Clips automáticos (discover) y Cola automática (auto_queue).
// desired = lo que dejaste en la web (true/false, o null si nunca lo tocaste). effective = lo que el worker dice que está haciendo.
const NAMES = ["discover", "auto_queue"] as const;
const msg = (m: string) => (/app_switches/i.test(m) ? "Falta correr 0015_interruptores.sql en Supabase" : m);

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, desired: { discover: null, auto_queue: null }, effective: { discover: null, auto_queue: null }, switches: false, networks: [], seenAt: null });
  const { data, error } = await db.from("app_switches").select("discover,auto_queue").eq("id", 1).maybeSingle();
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  const { data: ws } = await db.from("worker_status").select("info,seen_at").eq("id", 1).maybeSingle();
  const info = (ws?.info ?? {}) as { discover?: boolean; auto_queue?: boolean; switches?: boolean; networks?: string[] };
  return NextResponse.json({
    desired: { discover: data?.discover ?? null, auto_queue: data?.auto_queue ?? null },
    effective: { discover: typeof info.discover === "boolean" ? info.discover : null, auto_queue: typeof info.auto_queue === "boolean" ? info.auto_queue : null },
    switches: info.switches === true,           // el worker ya trae la Parte 13 (si no, hay que reconstruir el Docker)
    networks: info.networks ?? [],
    seenAt: ws?.seen_at ?? null,
  });
}

/** Cuerpo: { discover?: true|false|null, auto_queue?: true|false|null }. null = volver a lo que diga el .env. Solo cambia lo que mandes. */
export async function POST(req: Request) {
  const b = await req.json().catch(() => ({}));
  const patch: Record<string, boolean | null | string> = {};
  for (const n of NAMES) {
    if (!(n in b)) continue;
    if (b[n] !== true && b[n] !== false && b[n] !== null) return NextResponse.json({ error: "Valor no válido" }, { status: 400 });
    patch[n] = b[n];
  }
  if (!Object.keys(patch).length) return NextResponse.json({ error: "No mandaste ningún botón" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });
  const { error } = await db.from("app_switches").upsert({ id: 1, ...patch, updated_at: new Date().toISOString() });
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}
