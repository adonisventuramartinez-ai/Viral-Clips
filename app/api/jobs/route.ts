import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { insertJob } from "@/lib/jobs";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const ACTIVE = ["queued", "downloading", "recording", "transcribing", "analyzing", "clipping"];
// VercelFunctions admite ~4.5 MB por request. Los videos más grandes se suben directo a Storage
// con /api/uploads/sign y aquí solo llega la ruta (upload_path).
const MAX_INLINE_MB = 4;
const VIDEO_EXT: Record<string, string> = {
  mp4: "video/mp4", m4v: "video/mp4", mov: "video/quicktime",
  webm: "video/webm", mkv: "video/x-matroska", avi: "video/x-msvideo",
};

function parseMaybeJson(v: unknown) {
  if (typeof v !== "string" || !v.trim()) return v ?? null;
  try { return JSON.parse(v); } catch { return null; }
}

export async function POST(req: Request) {
  const ct = req.headers.get("content-type") || "";
  const isForm = ct.includes("multipart/form-data") || ct.includes("application/x-www-form-urlencoded");
  const form = isForm ? await req.formData().catch(() => null) : null;
  const body: Record<string, unknown> = form ? {} : ((await req.json().catch(() => ({}))) ?? {});
  const get = (key: string): unknown => (form ? form.get(key) ?? undefined : body[key]);

  const kind = String(get("kind") ?? "vod_url");
  const urlRaw = get("url");
  const url = typeof urlRaw === "string" ? urlRaw.trim() : "";
  const upload_path = String(get("upload_path") ?? "").trim();
  const fileVal = form?.get("file");
  const file = fileVal && typeof fileVal !== "string" && typeof (fileVal as File).arrayBuffer === "function"
    ? (fileVal as File) : null;

  if (!["vod_url", "live", "transform", "text_to_video"].includes(kind)) {
    return NextResponse.json({ error: "Tipo de trabajo no válido" }, { status: 400 });
  }

  // --- Validación de la entrada -------------------------------------------------
  if (kind === "text_to_video") {
    const promptRaw = get("prompt");
    const prompt = typeof promptRaw === "string" ? promptRaw.trim() : "";
    if (prompt.length < 5 || prompt.length > 600) {
      return NextResponse.json({ error: "Escribe una descripción de entre 5 y 600 caracteres." }, { status: 400 });
    }
  } else if (kind === "transform") {
    if (!file && !upload_path && !url) {
      return NextResponse.json({ error: "Sube un video o pega un link directo .mp4 para transformarlo." }, { status: 400 });
    }
    if (url && (!/^https?:\/\/\S+$/i.test(url) || url.length > 2000)) {
      return NextResponse.json({ error: "El link del video no es válido (debe empezar con https://)" }, { status: 400 });
    }
    if (upload_path && !/^incoming\/[0-9a-f-]{36}\.[a-z0-9]{2,5}$/i.test(upload_path)) {
      return NextResponse.json({ error: "La ruta del archivo subido no es válida. Vuelve a subirlo." }, { status: 400 });
    }
    if (file && !file.size) {
      return NextResponse.json({ error: "El archivo está vacío." }, { status: 400 });
    }
  } else {
    if (!url) return NextResponse.json({ error: kind === "live" ? "Falta el link del directo" : "Falta el link del video" }, { status: 400 });
    if (!/^https?:\/\/\S+$/i.test(url) || url.length > 500) {
      return NextResponse.json({ error: "El link no es válido (debe empezar con https://)" }, { status: 400 });
    }
  }

  const range_from = get("range_from") || null;
  const range_to = get("range_to") || null;
  const clip_seconds = get("clip_seconds") ?? 45;
  const clips = get("clips") ?? 15;
  const quality = get("quality") ?? "1080p";
  const review_minutes = get("review_minutes") ?? 2;
  const layout = get("layout") ?? "crop";
  const custom_crop = parseMaybeJson(get("custom_crop"));
  const clipper = get("clipper");
  const content_type = get("content_type") ?? "auto";
  const game = get("game");
  const progress_bar = get("progress_bar");
  const brand_template = get("brand_template");
  const bleep = get("bleep") ?? "auto";
  const loudnorm = get("loudnorm") ?? "auto";
  const zoom = get("zoom") ?? "auto";
  const slowmo = get("slowmo") ?? "auto";
  const tighten = get("tighten") ?? "auto";
  const max_new = get("max_new") ?? 3;
  const title = typeof get("title") === "string" ? String(get("title")).slice(0, 200) : "";

  // Crear con IA: el prompt viaja en el payload; el worker decide los 4 segmentos de 15 s.
  const IA_STYLES = ["realista", "anime", "cyberpunk", "cartoon", "3d"];
  const promptIA = kind === "text_to_video" ? String(get("prompt") ?? "").trim().slice(0, 600) : "";
  const styleIA = IA_STYLES.includes(String(get("style") ?? "")) ? String(get("style")) : "realista";
  const musicIA = get("music") === true || get("music") === "true" || get("music") === "1" || get("music") === "on";

  const num = (v: unknown, d: number, lo: number, hi: number) => {
    const n = Number(v);
    return Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.round(n))) : d;
  };
  const safe: Record<string, unknown> = {
    clip_seconds: Number(clip_seconds) === 0 || clip_seconds === "auto" ? 0 : num(clip_seconds, 45, 15, 120),
    clips: num(clips, 5, 1, 50),
    quality: ["720p", "1080p", "1440p", "2160p"].includes(String(quality)) ? String(quality) : "1080p",
    review_minutes: num(review_minutes, 2, 1, 10),
    ...(kind === "live" ? { max_new: num(max_new, 3, 1, 10) } : {}),
  };
  const safeType = ["auto", "reality", "podcast", "entrevista", "juego", "gta", "gta6", "gta_rp", "directo"]
    .includes(String(content_type)) ? String(content_type) : "auto";
  const safeGame = typeof game === "string" && game.trim() ? game.trim().slice(0, 60) : null;
  const tri = (v: unknown) => (v === "1" || v === true ? "1" : v === "0" || v === false ? "0" : "auto");
  const safeTpl = typeof brand_template === "string" && /^[a-z0-9-]{1,40}$/.test(brand_template) ? brand_template : null;
  const originalOn = !(get("original") === "0" || get("original") === false);
  const options: Record<string, unknown> = {
    content_type: safeType, game: safeGame, progress_bar: progress_bar === true || progress_bar === "true" || progress_bar === "1",
    brand_template: safeTpl, bleep: tri(bleep), loudnorm: tri(loudnorm), zoom: tri(zoom), slowmo: tri(slowmo), tighten: tri(tighten),
  };
  if (kind === "transform") options.original = originalOn;
  if (kind === "text_to_video") Object.assign(options, { prompt: promptIA, style: styleIA, music: musicIA });
  Object.assign(safe, options);
  const safeLayout = ["crop", "split", "split_eq", "split_game", "blur", "duo"].includes(String(layout)) ? String(layout) : "crop";
  const finalLayout = kind === "transform" || kind === "text_to_video" ? "crop" : safeLayout;

  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true, message: "Modo demo: conecta Supabase para encolar de verdad." });

  // --- Archivo del modo Transformar ---------------------------------------------
  let storedPath: string | null = null;
  let finalUrl = url;
  if (kind === "transform") {
    const signed = async (path: string) => {
      const r = await db.storage.from("uploads").createSignedUrl(path, 86400);
      const d = r.data as { signedUrl?: string; signedURL?: string } | null;
      return d?.signedUrl || d?.signedURL || "";
    };
    if (file) {
      if (file.size > MAX_INLINE_MB * 1024 * 1024) {
        return NextResponse.json({
          error: `El archivo pesa ${(file.size / 1024 / 1024).toFixed(1)} MB. Sube videos de más de ${MAX_INLINE_MB} MB desde la opción "Subir directo a Storage" o usa un link .mp4.`,
        }, { status: 413 });
      }
      if (file.type && !file.type.startsWith("video/")) {
        return NextResponse.json({ error: "El archivo debe ser un video." }, { status: 400 });
      }
      const ext = (file.name.split(".").pop() || "mp4").toLowerCase();
      const useExt = VIDEO_EXT[ext] ? ext : "mp4";
      storedPath = `incoming/${randomUUID()}.${useExt}`;
      const { error: upErr } = await db.storage.from("uploads").upload(
        storedPath, await file.arrayBuffer(), { contentType: VIDEO_EXT[useExt], upsert: false },
      );
      if (upErr) return NextResponse.json({ error: `No pude guardar el video: ${upErr.message}` }, { status: 500 });
      finalUrl = url || await signed(storedPath);
    } else if (upload_path) {
      storedPath = upload_path;
      finalUrl = url || await signed(upload_path);
    }
    if (!finalUrl) return NextResponse.json({ error: "No se pudo preparar la URL del video para el worker." }, { status: 500 });
  }

  if (kind === "live") {
    const { data: running } = await db.from("sources").select("id").eq("kind", "live").in("status", ACTIVE).limit(1);
    if (running && running.length) {
      return NextResponse.json({ error: "Ya hay un directo grabando. Páralo antes de empezar otro." }, { status: 409 });
    }
  }

  const row: Record<string, unknown> = {
    kind,
    url: finalUrl.trim() || null,
    range_from,
    range_to,
    status: "queued",
    layout: finalLayout,
    custom_crop,
    clipper: typeof clipper === "string" && clipper.trim() ? clipper.trim().slice(0, 40) : null,
  };
  if (kind === "transform") {
    row.storage_path = storedPath;
    row.title = title || null;
  } else if (kind === "text_to_video") {
    row.title = promptIA.slice(0, 100);
  }
  // Si aún no corriste 0005_calidad.sql no existe la columna "options": se reintenta sin ella.
  let ins = await db.from("sources").insert({ ...row, options }).select("id").single();
  if (ins.error && /options/i.test(ins.error.message)) ins = await db.from("sources").insert(row).select("id").single();
  const { data: source, error } = ins;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const jobType: "download" | "record" | "transform" | "text_to_video" =
    kind === "text_to_video" ? "text_to_video"
    : kind === "transform" ? "transform"
    : kind === "live" ? "record" : "download";
  const payload = kind === "text_to_video"
    ? { prompt: promptIA, style: styleIA, music: musicIA, text_to_video: true, clips: 4, clip_seconds: 15, total_seconds: 60, brand_template: safeTpl }
    : kind === "transform" ? { ...safe, transform: true, upload_path: storedPath, title }
    : safe;
  const { error: jobErr } = await insertJob(db, { source_id: source.id, payload }, jobType);
  if (jobErr) return NextResponse.json({ error: jobErr.message }, { status: 500 });

  return NextResponse.json({ ok: true, source_id: source.id, kind });
}
