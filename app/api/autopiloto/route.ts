import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { autorizadoWorker, leerConfig, projects } from "@/lib/autopilot";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const msg = (m: string) => {
  if (/violates check constraint|check constraint/i.test(m) && /network/i.test(m)) {
    return "Falta correr supabase/migrations/0020_autopiloto.sql en la Supabase de la web (abre las redes del piloto).";
  }
  if (/connections/i.test(m)) return "Falta correr 0013_conexiones.sql en la Supabase de la web";
  return m;
};

export async function GET() {
  const [cfg, proyectos] = await Promise.all([leerConfig(), projects()]);
  if (cfg.error) return NextResponse.json({ error: cfg.error }, { status: 500 });

  return NextResponse.json({
    config: cfg.data,
    projects: proyectos,
    pages: proyectos.flatMap((p) => p.paginas.map((page) => ({ ...page, project: p.nombre, projectId: p.id }))),
    status: {
      savedAt: cfg.data.updated_at ?? null,
      workerSyncsEvery: "15 s",
      queueEvery: "2 min",
    },
  });
}

/** La UI guarda la config; el worker la lee con la misma firma HMAC del secreto R2/Tigris. */
export async function POST(req: NextRequest) {
  const raw = await req.text();
  let b: any = {};
  try {
    b = raw ? JSON.parse(raw) : {};
  } catch {
    return NextResponse.json({ error: "JSON inválido" }, { status: 400 });
  }

  // El worker solo pide la config: no cambia nada aquí.
  if (autorizadoWorker(raw, req.headers.get("x-autopiloto")) && b.worker === true) {
    const cfg = await leerConfig();
    if (cfg.error) return NextResponse.json({ ok: false, error: cfg.error }, { status: 500 });
    return NextResponse.json({ ok: true, config: cfg.data });
  }

  const action = String(b.action ?? "");
  const db = supabaseAdmin;

  if (action === "apagar") {
    const cfg = await leerConfig();
    if (cfg.error) return NextResponse.json({ error: cfg.error }, { status: 500 });
    const r = await db.from("connections").upsert({
      network: "autopilot",
      data: { enabled: false, page_ids: cfg.data.page_ids, auto_approve: false, max_per_run: cfg.data.max_per_run },
      updated_at: new Date().toISOString(),
    });
    if (r.error) return NextResponse.json({ error: msg(r.error.message) }, { status: 500 });
    return NextResponse.json({ ok: true, queued: 0, page_ids: cfg.data.page_ids });
  }

  if (action === "config" || action === "encender" || action === "encolar") {
    const current = await leerConfig();
    if (current.error) return NextResponse.json({ error: current.error }, { status: 500 });
    const rawPages = b.page_ids === undefined ? current.data.page_ids : b.page_ids;
    const page_ids = (Array.isArray(rawPages) ? rawPages : []).map(String).filter((x) => /^\d+$/.test(x));
    if ((action === "encender" || action === "encolar") && !page_ids.length) {
      return NextResponse.json({ error: "Conecta una cuenta de Facebook y elige al menos una página" }, { status: 400 });
    }
    const max_per_run = Math.max(1, Math.min(25, Number(b.max_per_run ?? current.data.max_per_run) || 5));
    const auto_approve = action === "encender" ? true : b.auto_approve === undefined ? current.data.auto_approve : Boolean(b.auto_approve);
    const r = await db.from("connections").upsert({
      network: "autopilot",
      data: {
        enabled: action === "encender" ? true : current.data.enabled,
        page_ids,
        auto_approve,
        max_per_run,
      },
      updated_at: new Date().toISOString(),
    });
    if (r.error) return NextResponse.json({ error: msg(r.error.message) }, { status: 500 });

    // El worker lee el cambio en <=15 s y encola en <=2 min. No escribimos tabs del worker desde aquí.
    return NextResponse.json({ ok: true, queued: 0, warnings: [], page_ids });
  }

  return NextResponse.json({ error: "Acción desconocida" }, { status: 400 });
}
