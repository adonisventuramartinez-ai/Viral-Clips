import { NextRequest, NextResponse } from "next/server";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";
import { parsearTrendsRss } from "@/lib/tendencias";

export const dynamic = "force-dynamic";

// Caché en memoria 30 min por país (no se castiga a Google en cada apertura de la ventana)
const cache = new Map<string, { t: number; xml: string }>();

// GET /api/tendencias?geo=DO&desc=texto  →  { geo, tendencias: [...] }
export async function GET(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  const url = new URL(req.url);
  const geoPedido = (url.searchParams.get("geo") || process.env.TRENDS_GEO || "DO").toUpperCase();
  const geo = /^[A-Z]{2}$/.test(geoPedido) ? geoPedido : "DO";
  const desc = (url.searchParams.get("desc") || "").slice(0, 600);

  try {
    let xml = cache.get(geo);
    if (!xml || Date.now() - xml.t > 30 * 60_000) {
      const r = await fetch(`https://trends.google.com/trending/rss?geo=${geo}`, {
        headers: { "User-Agent": "Mozilla/5.0 (compatible; fb-web-publisher)", Accept: "application/rss+xml, text/xml" },
        signal: AbortSignal.timeout(10_000),
        cache: "no-store",
      });
      if (!r.ok) throw new Error(`Google Trends respondió ${r.status}`);
      xml = { t: Date.now(), xml: await r.text() } as any;
      cache.set(geo, xml as any);
    }
    return NextResponse.json({ geo, tendencias: parsearTrendsRss((xml as any).xml, desc) });
  } catch (e: any) {
    return NextResponse.json({ geo, tendencias: [], error: e?.message || "No se pudieron cargar las tendencias" });
  }
}

