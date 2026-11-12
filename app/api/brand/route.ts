import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Logo / marca de agua: se guarda en Storage (bucket "uploads", carpeta "brand/") y el worker lo pega en cada clip.
const BUCKET = "uploads";
const SETTINGS = "brand/settings.json";
const POS = ["bc", "bl", "br", "tc", "tl", "tr"];
const EXT: Record<string, string> = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp" };

type Subs = { text: string; active: string; outline: string; size: number; outline_w: number; upper: boolean; pop: boolean; offset: number };
type Settings = { enabled: boolean; pos: string; size: number; opacity: number; file?: string; subs?: Subs; hook: boolean; hook_sec: number };
const DEFAULT: Settings = { enabled: true, pos: "bc", size: 24, opacity: 100, hook: true, hook_sec: 3.5 };
const hex = (v: unknown, d: string) => (/^#?[0-9a-fA-F]{6}$/.test(String(v)) ? String(v).replace("#", "").toUpperCase() : d);

async function readSettings(db: any): Promise<Settings> {
  const { data } = await db.storage.from(BUCKET).download(SETTINGS);
  if (!data) return { ...DEFAULT };
  try { return { ...DEFAULT, ...JSON.parse(await data.text()) }; } catch { return { ...DEFAULT }; }
}

async function writeSettings(db: any, s: Settings) {
  const body = new Blob([JSON.stringify(s)], { type: "application/json" });
  return db.storage.from(BUCKET).upload(SETTINGS, body, { upsert: true, contentType: "application/json" });
}

const clamp = (v: unknown, lo: number, hi: number, d: number) => { const n = Number(v); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.round(n))) : d; };

export async function GET() {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ demo: true, settings: DEFAULT, logoUrl: null });
  const settings = await readSettings(db);
  let logoUrl: string | null = null;
  if (settings.file) {
    const { data } = await db.storage.from(BUCKET).createSignedUrl(settings.file, 3600);
    logoUrl = data?.signedUrl ?? null;
  }
  return NextResponse.json({ settings, logoUrl });
}

export async function POST(req: Request) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ error: "Conecta Supabase para guardar el logo" }, { status: 503 });

  const form = await req.formData().catch(() => null);
  if (!form) return NextResponse.json({ error: "Datos no válidos" }, { status: 400 });
  const cur = await readSettings(db);
  const next: Settings = { ...cur };
  if (form.has("enabled")) next.enabled = form.get("enabled") !== "false";
  if (form.has("pos") && POS.includes(String(form.get("pos")))) next.pos = String(form.get("pos"));
  if (form.has("size")) next.size = clamp(form.get("size"), 5, 60, cur.size);
  if (form.has("opacity")) next.opacity = clamp(form.get("opacity"), 10, 100, cur.opacity);

  // subtítulos y texto gancho (la web manda un JSON en "subs")
  const rawSubs = form.get("subs");
  if (typeof rawSubs === "string" && rawSubs) {
    try {
      const s = JSON.parse(rawSubs);
      next.subs = {
        text: hex(s.text, "FFFFFF"), active: hex(s.active, "FFE000"), outline: hex(s.outline, "000000"),
        size: clamp(s.size, 40, 140, 86), outline_w: clamp(s.outline_w, 0, 14, 7),
        upper: s.upper !== false, pop: s.pop !== false, offset: clamp(s.offset, -400, 600, 0),
      };
    } catch { return NextResponse.json({ error: "Estilo de subtítulos no válido" }, { status: 400 }); }
  }
  if (form.get("hook") !== null) next.hook = form.get("hook") !== "false";
  if (form.get("hook_sec") !== null) next.hook_sec = Math.min(8, Math.max(1.5, Number(form.get("hook_sec")) || 3.5));

  const file = form.get("file");
  if (file && typeof file !== "string" && file.size > 0) {
    const ext = EXT[file.type];
    if (!ext) return NextResponse.json({ error: "El logo debe ser PNG, JPG o WEBP (mejor PNG con fondo transparente)" }, { status: 400 });
    if (file.size > 3 * 1024 * 1024) return NextResponse.json({ error: "El logo pesa más de 3 MB" }, { status: 400 });
    const path = `brand/logo.${ext}`;
    if (cur.file && cur.file !== path) await db.storage.from(BUCKET).remove([cur.file]);
    const { error } = await db.storage.from(BUCKET).upload(path, Buffer.from(await file.arrayBuffer()), { upsert: true, contentType: file.type });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    next.file = path;
  }

  const { error } = await writeSettings(db, next);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, settings: next });
}

export async function DELETE() {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const cur = await readSettings(db);
  if (cur.file) await db.storage.from(BUCKET).remove([cur.file]);
  const { file: _f, ...rest } = cur;
  await writeSettings(db, rest);
  return NextResponse.json({ ok: true });
}
