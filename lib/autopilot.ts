import crypto from "crypto";
import { supabaseAdmin } from "./db";
import { limpiarEnv } from "./env";
import { desencriptar } from "./crypto";
import { GRAPH_BASE } from "./graph";

export type Page = { id: string; name: string };
export type Project = { id: number; nombre: string; paginas: Page[]; error?: string };
export type AutopilotConfig = {
  enabled: boolean;
  page_ids: string[];
  auto_approve: boolean;
  max_per_run: number;
  updated_at?: string | null;
};

/**
 * Worker y web pueden estar en Supabase distintos. El puente se firma con el secreto
 * de Tigris/R2, que ya existe en worker/.env y en Vercel (mismo valor, sin enviarlo nunca).
 */
function secretoCompartido(): string {
  return limpiarEnv(process.env.R2_SECRET_ACCESS_KEY || "");
}

export function autorizadoWorker(rawBody: string, header: string | null): boolean {
  const secreto = secretoCompartido();
  const firma = (header || "").trim();
  if (!secreto || !/^[a-f0-9]{64}$/i.test(firma)) return false;
  const esperada = crypto.createHmac("sha256", secreto).update(rawBody).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(esperada, "hex"), Buffer.from(firma, "hex"));
}

export async function leerConfig(): Promise<{ error: string | null; data: AutopilotConfig }> {
  const vacia: AutopilotConfig = { enabled: false, page_ids: [], auto_approve: true, max_per_run: 5, updated_at: null };
  if (!secretoCompartido()) return { error: "Falta R2_SECRET_ACCESS_KEY en Vercel (la misma de worker/.env)", data: vacia };
  const { data, error } = await supabaseAdmin
    .from("connections")
    .select("data,updated_at")
    .eq("network", "autopilot")
    .maybeSingle();
  if (error) {
    const m = /check constraint/i.test(error.message) && /network/i.test(error.message)
      ? "Falta correr 0020_autopiloto.sql en la Supabase de la web"
      : /connections/i.test(error.message)
        ? "Falta correr 0013_conexiones.sql en la Supabase de la web"
        : error.message;
    return { error: m, data: vacia };
  }
  const d = (data?.data ?? {}) as Record<string, unknown>;
  return {
    error: null,
    data: {
      enabled: Boolean(d.enabled),
      page_ids: (Array.isArray(d.page_ids) ? d.page_ids : []).map(String).filter((x) => /^\d+$/.test(x)),
      auto_approve: d.auto_approve === undefined ? true : Boolean(d.auto_approve),
      max_per_run: Math.max(1, Math.min(25, Number(d.max_per_run) || 5)),
      updated_at: data?.updated_at ?? null,
    },
  };
}

/** Cuentas de Facebook conectadas por OAuth (proyectos) y sus páginas. Nunca devuelve tokens. */
export async function projects(): Promise<Project[]> {
  let data: any[] = [];
  try {
    const r = await supabaseAdmin
      .from("cuentas_fb")
      .select("id,nombre,token_encriptado,token_invalido_en")
      .order("creado_en", { ascending: false });
    if (r.error) {
      const again = await supabaseAdmin.from("cuentas_fb").select("id,nombre,token_encriptado").order("creado_en", { ascending: false });
      if (again.error) return [];
      data = again.data ?? [];
    } else {
      data = r.data ?? [];
    }
  } catch {
    return [];
  }

  return Promise.all(
    data.map(async (cuenta): Promise<Project> => {
      const out: Project = { id: Number(cuenta.id), nombre: String(cuenta.nombre || "Cuenta"), paginas: [] };
      if (cuenta.token_invalido_en) {
        out.error = "Token vencido: reconecta la cuenta en /facebook";
        return out;
      }
      try {
        const token = desencriptar(String(cuenta.token_encriptado || ""));
        const res = await fetch(
          `${GRAPH_BASE}/me/accounts?access_token=${encodeURIComponent(token)}&fields=id,name&limit=200`,
          { cache: "no-store", signal: AbortSignal.timeout(15000) },
        );
        const j: any = await res.json();
        if (j?.error) {
          out.error = j.error.message || "Facebook rechazó el token";
          return out;
        }
        out.paginas = (j.data || [])
          .filter((p: any) => /^\d+$/.test(String(p.id)))
          .map((p: any) => ({ id: String(p.id), name: String(p.name || p.id) }));
      } catch (e: any) {
        out.error = e?.message?.slice(0, 120) || "No se pudieron leer las páginas";
      }
      return out;
    }),
  );
}

/** Token fresco de una página, buscando en todos los proyectos conectados. Nunca se devuelve al navegador. */
export async function tokenDePagina(pageId: string): Promise<{ token: string; cuenta: number | null; error?: string }> {
  const { data: cuentas, error } = await supabaseAdmin
    .from("cuentas_fb")
    .select("id,token_encriptado")
    .order("creado_en", { ascending: false });
  if (error || !cuentas?.length) return { token: "", cuenta: null, error: "No hay cuentas de Facebook conectadas" };
  for (const cuenta of cuentas) {
    try {
      const token = desencriptar(String(cuenta.token_encriptado || ""));
      const res = await fetch(
        `${GRAPH_BASE}/me/accounts?access_token=${encodeURIComponent(token)}&fields=id,name,access_token&limit=200`,
        { cache: "no-store", signal: AbortSignal.timeout(15000) },
      );
      const j: any = await res.json();
      const page = (j.data || []).find((p: any) => String(p.id) === pageId);
      if (page?.access_token) return { token: String(page.access_token), cuenta: Number(cuenta.id) };
    } catch {
      // otra cuenta puede tener la página; seguimos
    }
  }
  return { token: "", cuenta: null, error: "Esa página no pertenece a ninguna cuenta conectada" };
}
