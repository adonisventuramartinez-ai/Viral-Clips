import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, usedBytes: 0, clips: 0 });
  const { data, error } = await db.from("clips").select("size_bytes");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  const usedBytes = (data ?? []).reduce((a, r) => a + (r.size_bytes ?? 0), 0);
  return NextResponse.json({ usedBytes, clips: data?.length ?? 0 });
}
