import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Plantillas de marca: cada una es una copia de la configuración de Ajustes > Marca (logo, subtítulos, gancho) con nombre.
// Se guardan en brand/templates.json y el worker las usa cuando el trabajo trae brand_template = id.
const BUCKET = "uploads";
const SETTINGS = "brand/settings.json";
const FILE = "brand/templates.json";
const MAX = 12;

type Item = { name: string; settings: Record<string, any> };
type Store = { items: Record<string, Item> };

async function readJson(db: any, path: string): Promise<any> {
  const { data } = await db.storage.from(BUCKET).download(path);
  if (!data) return null;
  try { return JSON.parse(await data.text()); } catch { return null; }
}
async function writeJson(db: any, path: string, obj: unknown) {
  return db.storage.from(BUCKET).upload(path, new Blob([JSON.stringify(obj)], { type: "application/json" }), { upsert: true, contentType: "application/json" });
}
const readStore = async (db: any): Promise<Store> => { const s = await readJson(db, FILE); return s && typeof s.items === "object" ? s : { items: {} }; };

const slug = (name: string, taken: string[]) => {
  const base = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 30) || "marca";
  let id = base, n = 2;
  while (taken.includes(id)) id = `${base}-${n++}`;
  return id;
};

async function copyFile(db: any, from: string, to: string) {
  const { data } = await db.storage.from(BUCKET).download(from);
  if (!data) return false;
  const ext = from.split(".").pop() || "png";
  const dest = to.replace(/\.[^.]+$/, "") + "." + ext;
  const { error } = await db.storage.from(BUCKET).upload(dest, Buffer.from(await data.arrayBuffer()), { upsert: true, contentType: data.type || "image/png" });
  return error ? false : dest;
}

export async function GET() {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ demo: true, items: [] });
  const store = await readStore(db);
  const items = Object.entries(store.items).map(([id, it]) => ({
    id, name: it.name, hasLogo: !!it.settings?.file, pos: it.settings?.pos ?? "bc", hook: it.settings?.hook !== false,
    color: it.settings?.subs?.active ?? "FFE000",
  }));
  return NextResponse.json({ items });
}

/** { name } guarda la marca actual como plantilla nueva · { apply: id } pasa una plantilla a la marca general · { rename: id, name } */
export async function POST(req: Request) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ error: "Conecta Supabase para guardar plantillas" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const store = await readStore(db);

  if (typeof b.apply === "string") {
    const it = store.items[b.apply];
    if (!it) return NextResponse.json({ error: "Esa plantilla ya no existe" }, { status: 404 });
    const settings = { ...it.settings };
    if (settings.file) {
      const dest = await copyFile(db, settings.file, "brand/logo.png");
      if (dest) settings.file = dest; else delete settings.file;
    }
    const { error } = await writeJson(db, SETTINGS, settings);
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, settings });
  }

  if (typeof b.rename === "string") {
    const it = store.items[b.rename];
    const name = String(b.name ?? "").trim().slice(0, 40);
    if (!it || !name) return NextResponse.json({ error: "Escribe el nombre nuevo" }, { status: 400 });
    it.name = name;
    await writeJson(db, FILE, store);
    return NextResponse.json({ ok: true });
  }

  const name = String(b.name ?? "").trim().slice(0, 40);
  if (!name) return NextResponse.json({ error: "Ponle un nombre a la plantilla" }, { status: 400 });
  if (Object.keys(store.items).length >= MAX) return NextResponse.json({ error: `Máximo ${MAX} plantillas. Borra alguna.` }, { status: 400 });
  const cur = (await readJson(db, SETTINGS)) ?? {};
  const id = slug(name, Object.keys(store.items));
  const settings = { ...cur };
  if (settings.file) {   // copia propia del logo: si luego cambias el logo general, esta plantilla no se altera
    const dest = await copyFile(db, settings.file, `brand/templates/${id}.png`);
    if (dest) settings.file = dest; else delete settings.file;
  }
  store.items[id] = { name, settings };
  const { error } = await writeJson(db, FILE, store);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, id });
}

export async function DELETE(req: Request) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const { id } = await req.json().catch(() => ({}));
  const store = await readStore(db);
  const it = typeof id === "string" ? store.items[id] : null;
  if (!it) return NextResponse.json({ error: "Esa plantilla ya no existe" }, { status: 404 });
  if (it.settings?.file) await db.storage.from(BUCKET).remove([it.settings.file]);
  delete store.items[id];
  await writeJson(db, FILE, store);
  return NextResponse.json({ ok: true });
}
