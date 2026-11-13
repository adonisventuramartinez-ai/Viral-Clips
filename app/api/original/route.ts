import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Ajustes del Modo Original (voz narradora, dramómetro, encuesta, TOP, crédito). El worker los lee de Storage.
const BUCKET = "uploads";
const FILE = "brand/original.json";
const VOICES = ["es-DO-EmilioNeural", "es-DO-RamonaNeural", "es-MX-JorgeNeural", "es-MX-DaliaNeural", "es-US-AlonsoNeural", "es-ES-AlvaroNeural"];

type Original = { enabled: boolean; show: string; page: string; credit: string; narrate: boolean; voice: string; meter: boolean; poll: boolean; top: boolean; top_n: number };
const DEFAULT: Original = {
  enabled: true, show: "La Casa de Alofoke 3", page: "", credit: "Contenido de La Casa de Alofoke, usado con permiso de Alofoke.",
  narrate: true, voice: "es-DO-EmilioNeural", meter: true, poll: true, top: true, top_n: 5,
};

async function read(db: any): Promise<Original> {
  const { data } = await db.storage.from(BUCKET).download(FILE);
  if (!data) return { ...DEFAULT };
  try { return { ...DEFAULT, ...JSON.parse(await data.text()) }; } catch { return { ...DEFAULT }; }
}

export async function GET() {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ demo: true, settings: DEFAULT, voices: VOICES });
  return NextResponse.json({ settings: await read(db), voices: VOICES });
}

export async function POST(req: Request) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ error: "Conecta Supabase para guardar" }, { status: 503 });
  const b = await req.json().catch(() => null);
  if (!b || typeof b !== "object") return NextResponse.json({ error: "Datos no válidos" }, { status: 400 });
  const cur = await read(db);
  const str = (v: unknown, d: string, max: number) => (typeof v === "string" ? v.trim().slice(0, max) : d);
  const next: Original = {
    enabled: b.enabled !== false,
    show: str(b.show, cur.show, 80) || DEFAULT.show,
    page: str(b.page, cur.page, 60),
    credit: str(b.credit, cur.credit, 200),
    narrate: b.narrate !== false,
    voice: VOICES.includes(b.voice) ? b.voice : cur.voice,
    meter: b.meter !== false,
    poll: b.poll !== false,
    top: b.top !== false,
    top_n: Math.min(10, Math.max(3, Math.round(Number(b.top_n)) || cur.top_n)),
  };
  const body = new Blob([JSON.stringify(next)], { type: "application/json" });
  const { error } = await db.storage.from(BUCKET).upload(FILE, body, { upsert: true, contentType: "application/json" });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, settings: next });
}
