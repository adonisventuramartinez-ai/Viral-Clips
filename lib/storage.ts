// Storage del bucket 'clips': Supabase o Cloudflare R2 según STORAGE_DRIVER.
// El bucket 'uploads' y el de publicaciones de Facebook NO pasan por aquí.
import type { SupabaseClient } from "@supabase/supabase-js";

const CLIPS_BUCKET = "clips";

export function clipsOnR2(): boolean {
  return (process.env.STORAGE_DRIVER || "supabase").trim().toLowerCase() === "r2";
}

let cached: any = null;

async function s3() {
  if (!cached) {
    const { S3Client } = await import("@aws-sdk/client-s3");
    const account = process.env.R2_ACCOUNT_ID || "";
    const endpoint = process.env.R2_ENDPOINT || (account ? `https://${account}.r2.cloudflarestorage.com` : "");
    if (!endpoint) throw new Error("Falta R2_ACCOUNT_ID o R2_ENDPOINT en el entorno");
    cached = new S3Client({
      endpoint,
      region: process.env.R2_REGION || "auto",
      credentials: {
        accessKeyId: process.env.R2_ACCESS_KEY_ID || "",
        secretAccessKey: process.env.R2_SECRET_ACCESS_KEY || "",
      },
    });
  }
  return cached;
}

export type SignedClip = { path: string; signedUrl: string | null };

function r2Ready(): boolean {
  const endpoint = process.env.R2_ENDPOINT || (process.env.R2_ACCOUNT_ID ? `https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com` : "");
  return Boolean(endpoint && process.env.R2_ACCESS_KEY_ID && process.env.R2_SECRET_ACCESS_KEY);
}

/** Estado SIN secretos, para saber qué deployment está usando qué almacenaje. */
export function storageStatus() {
  return {
    driver: clipsOnR2() ? "r2" : "supabase",
    endpointSet: Boolean(process.env.R2_ENDPOINT || process.env.R2_ACCOUNT_ID),
    accessKeySet: Boolean(process.env.R2_ACCESS_KEY_ID),
    secretSet: Boolean(process.env.R2_SECRET_ACCESS_KEY),
    bucket: process.env.R2_CLIPS_BUCKET || CLIPS_BUCKET,
    region: process.env.R2_REGION || "auto",
  };
}

/** Prueba real contra S3 (sin exponer llaves): detecta claves viejas en Vercel. */
export async function probeR2(): Promise<{ ok: boolean; code?: string; error?: string }> {
  if (!clipsOnR2()) return { ok: true };
  if (!r2Ready()) return { ok: false, error: "Faltan variables R2 en este deployment" };
  try {
    const { HeadBucketCommand } = await import("@aws-sdk/client-s3");
    const client = await s3();
    await client.send(new HeadBucketCommand({ Bucket: process.env.R2_CLIPS_BUCKET || CLIPS_BUCKET }));
    return { ok: true };
  } catch (e: any) {
    const code = String(e?.name || e?.Code || "Error");
    const raw = String(e?.message || e);
    const safe = /InvalidAccessKeyId|access key/i.test(raw)
      ? "La Access Key ID no existe: actualízala en Vercel y redeploya."
      : raw.slice(0, 160);
    return { ok: false, code, error: safe };
  }
}

async function signR2(paths: string[], seconds: number, download: boolean): Promise<SignedClip[]> {
  if (!r2Ready()) return paths.map((path) => ({ path, signedUrl: null }));
  const { GetObjectCommand } = await import("@aws-sdk/client-s3");
  const { getSignedUrl } = await import("@aws-sdk/s3-request-presigner");
  const bucket = process.env.R2_CLIPS_BUCKET || CLIPS_BUCKET;
  const client = await s3();
  return Promise.all(
    paths.map(async (path) => {
      try {
        const params: any = { Bucket: bucket, Key: path };
        if (download) {
          const name = path.split("/").pop()?.replace(/"/g, "") || "clip.mp4";
          params.ResponseContentDisposition = `attachment; filename="${name}"`;
        }
        return { path, signedUrl: await getSignedUrl(client, new GetObjectCommand(params), { expiresIn: seconds }) };
      } catch (e) {
        console.error("No se pudo firmar en R2:", path, e);
        return { path, signedUrl: null };
      }
    }),
  );
}

async function signSupabase(paths: string[], seconds: number, download: boolean, db?: SupabaseClient): Promise<SignedClip[]> {
  try {
    const client = db ?? (await import("./db")).supabaseAdmin;
    const { data } = await client.storage.from(CLIPS_BUCKET).createSignedUrls(
      paths,
      seconds,
      download ? { download: true } : undefined,
    );
    const byPath = new Map<string, string>();
    (data || []).forEach((x: any) => {
      if (x?.path && x?.signedUrl) byPath.set(x.path, x.signedUrl);
    });
    return paths.map((path) => ({ path, signedUrl: byPath.get(path) ?? null }));
  } catch (e) {
    console.error("No se pudo firmar en Supabase:", e);
    return paths.map((path) => ({ path, signedUrl: null }));
  }
}

/** Firma rutas de clips. Si el driver elegido falla, usa el otro automáticamente. */
export async function signClipPaths(
  paths: string[],
  seconds = 3600,
  download = false,
  db?: SupabaseClient,
): Promise<SignedClip[]> {
  if (!paths.length) return [];
  const preferR2 = clipsOnR2();
  const first = preferR2 ? await signR2(paths, seconds, download) : await signSupabase(paths, seconds, download, db);
  const missing = first.filter((x) => !x.signedUrl).map((x) => x.path);
  if (!missing.length) return first;
  const backup = preferR2 ? await signSupabase(missing, seconds, download, db) : await signR2(missing, seconds, download);
  const byPath = new Map(backup.map((x) => [x.path, x.signedUrl]));
  return first.map((x) => (x.signedUrl ? x : { path: x.path, signedUrl: byPath.get(x.path) ?? null }));
}

/** Borra archivos del bucket de clips (R2 o Supabase, con respaldo automático). */
export async function removeClipFiles(paths: string[], db?: SupabaseClient): Promise<{ error: string | null }> {
  const clean = paths.filter(Boolean);
  if (!clean.length) return { error: null };

  const removeR2 = async () => {
    const { DeleteObjectsCommand } = await import("@aws-sdk/client-s3");
    const bucket = process.env.R2_CLIPS_BUCKET || CLIPS_BUCKET;
    await (await s3()).send(
      new DeleteObjectsCommand({ Bucket: bucket, Delete: { Objects: clean.map((Key) => ({ Key })) } }),
    );
  };
  const removeSb = async () => {
    const client = db ?? (await import("./db")).supabaseAdmin;
    const { error } = await client.storage.from(CLIPS_BUCKET).remove(clean);
    if (error) throw new Error(error.message);
  };

  const first = clipsOnR2() ? removeR2 : removeSb;
  const second = clipsOnR2() ? removeSb : removeR2;
  try {
    await first();
    return { error: null };
  } catch (e: any) {
    try {
      await second();
      return { error: null };
    } catch (e2: any) {
      return { error: e2?.message || e?.message || String(e) };
    }
  }
}
