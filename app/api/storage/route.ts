import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { probeR2, storageStatus } from "@/lib/storage";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

export async function GET() {
  const [storage, db] = await Promise.all([probeR2(), Promise.resolve(serverClient())]);
  const info = { ...storageStatus(), probe: storage };
  if (!db) return NextResponse.json({ demo: true, usedBytes: 0, clips: 0, storage: info });
  const { data, error } = await db.from("clips").select("size_bytes");
  if (error) return NextResponse.json({ error: error.message, storage: info }, { status: 500 });
  const usedBytes = (data ?? []).reduce((a, r) => a + (r.size_bytes ?? 0), 0);
  return NextResponse.json({ usedBytes, clips: data?.length ?? 0, storage: info });
}
