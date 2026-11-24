import type { SupabaseClient } from "@supabase/supabase-js";
import { fmtTime } from "./format";
import type { Clip, Pack, Viral } from "./types";

type Row = {
  id: string;
  title: string;
  start_sec: number;
  end_sec: number;
  viral_score: number;
  reason: string | null;
  storage_path: string | null;
  size_bytes: number | null;
  is_public?: boolean | null;
  description?: string | null;
  hashtags?: string[] | null;
  pack?: Pack | null;
  thumb_path?: string | null;
  scheduled_at?: string | null;
  publish_status?: "scheduled" | "published" | "error" | null;
  publish_error?: string | null;
  viral?: Viral | null;
  viral_status?: Clip["viralStatus"] | null;
  thumb_b_path?: string | null;
  thumb_choice?: "a" | "b" | null;
};

const COLS = "id,title,start_sec,end_sec,viral_score,reason,storage_path,size_bytes";

/** Clips (más nuevos primero) con URLs firmadas para ver y descargar. sourceId opcional. */
export async function loadClips(db: SupabaseClient, sourceId?: string): Promise<Clip[]> {
  const q = (cols: string) => {
    const base = db.from("clips").select(cols);
    return (sourceId ? base.eq("source_id", sourceId) : base).order("created_at", { ascending: false }).limit(200);
  };
  // Prueba con todas las columnas nuevas y va quitando las que aún no existan (migraciones 0004 / 0005 / 0007 sin correr)
  let data: unknown[] | null = null;
  let error: { message: string } | null = null;
  for (const extra of [",is_public,description,hashtags,pack,thumb_path,scheduled_at,publish_status,publish_error,viral,viral_status,thumb_b_path,thumb_choice", ",is_public,description,hashtags,pack,thumb_path,scheduled_at,publish_status,publish_error,viral,viral_status,thumb_b_path", ",is_public,description,hashtags,pack,thumb_path,scheduled_at,publish_status,publish_error", ",is_public,description,hashtags", ",is_public", ""]) {
    const r = await q(COLS + extra);
    data = r.data as unknown[] | null;
    error = r.error;
    if (!error) break;
  }
  if (error) throw new Error(error.message);

  const rows = (data ?? []) as unknown as Row[];
  const paths = rows.flatMap((r) => [r.storage_path, r.thumb_path, r.thumb_b_path]).filter((p): p is string => !!p);
  const play = new Map<string, string>();
  const dl = new Map<string, string>();
  if (paths.length) {
    const bucket = db.storage.from("clips");
    const [a, b] = await Promise.all([
      bucket.createSignedUrls(paths, 3600),
      bucket.createSignedUrls(paths, 3600, { download: true }),
    ]);
    a.data?.forEach((x) => x.path && x.signedUrl && play.set(x.path, x.signedUrl));
    b.data?.forEach((x) => x.path && x.signedUrl && dl.set(x.path, x.signedUrl));
  }

  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    start: fmtTime(r.start_sec),
    end: fmtTime(r.end_sec),
    score: r.viral_score,
    seconds: Math.round(r.end_sec - r.start_sec),
    path: r.storage_path ?? undefined,
    startSec: Number(r.start_sec),
    endSec: Number(r.end_sec),
    sizeMb: Math.round(((r.size_bytes ?? 0) / 1048576) * 10) / 10,
    captions: "",
    thumb: "",
    reason: r.reason ?? undefined,
    isPublic: r.is_public ?? true,
    description: r.description ?? undefined,
    hashtags: r.hashtags ?? undefined,
    pack: r.pack ?? undefined,
    thumbUrl: r.thumb_path ? play.get(r.thumb_path) : undefined,
    scheduledAt: r.scheduled_at ?? undefined,
    publishStatus: r.publish_status ?? undefined,
    publishError: r.publish_error ?? undefined,
    viral: r.viral ?? undefined,
    viralStatus: r.viral_status ?? undefined,
    thumbBUrl: r.thumb_b_path ? play.get(r.thumb_b_path) : undefined,
    thumbChoice: r.thumb_choice === "b" ? "b" : "a",
    videoUrl: r.storage_path ? play.get(r.storage_path) : undefined,
    downloadUrl: r.storage_path ? dl.get(r.storage_path) : undefined,
  }));
}

/** true si el worker dio señales de vida en los últimos 45 s. */
export async function workerOnline(db: SupabaseClient): Promise<boolean> {
  const { data } = await db.from("worker_status").select("seen_at").eq("id", 1).maybeSingle();
  if (!data) return false;
  return Date.now() - new Date(data.seen_at as string).getTime() < 45000;
}
