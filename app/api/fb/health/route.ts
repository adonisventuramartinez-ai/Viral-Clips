import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";

export const dynamic = "force-dynamic";

// Pública y mínima, para monitores de disponibilidad (UptimeRobot, Better Stack…).
// No revela configuración: solo si la app y la base de datos responden.
// El detalle completo está en /api/admin/diagnostico (requiere sesión de admin).
export async function GET() {
  let db = false;
  try {
    const { error } = await supabaseAdmin.from("cron_latido").select("id").limit(1);
    db = !error;
  } catch {
    db = false;
  }
  return NextResponse.json({ ok: db, db }, { status: db ? 200 : 503, headers: { "Cache-Control": "no-store" } });
}

