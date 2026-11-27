// Métricas reales de Facebook (vistas, alcance, reacciones...) por publicación.
//
// Meta cambia los nombres de las métricas cada cierto tiempo (en nov-2025 retiró
// varias de "impresiones" y las reemplazó por "views"). Por eso NADA aquí depende
// de un solo nombre: cada dato tiene una cadena de intentos y se usa el primero que
// Facebook acepte. Si todos fallan, se devuelve el motivo para mostrarlo en el panel.
//
// Lógica sin red propia: `graph` se inyecta, así se puede probar sin Facebook.

import type { TipoContenido } from "./facebook";

export type GraphFn = (ruta: string, params?: Record<string, string>) => Promise<any>;

export interface Metricas {
  vistas: number | null;
  alcance: number | null;
  reacciones: number | null;
  comentarios: number | null;
  compartidos: number | null;
  permalink: string | null;
  publicadoEn: string | null;
  /** Qué métrica respondió (útil para depurar cuando Meta cambia nombres). */
  fuente: string | null;
  /** Primer error "de verdad" (permiso, token...) para mostrar al usuario. */
  error: string | null;
  codigoError: number | null;
}

export const VACIAS: Metricas = {
  vistas: null, alcance: null, reacciones: null, comentarios: null, compartidos: null,
  permalink: null, publicadoEn: null, fuente: null, error: null, codigoError: null,
};

interface Intento { ruta: (id: string) => string; metrica: string }

// Orden: primero lo más nuevo, al final lo viejo (por si la app usa una versión antigua de la API).
export function intentosVistas(tipo: TipoContenido): Intento[] {
  const base: Intento[] = [{ ruta: (id) => `${id}/insights`, metrica: "post_media_view" }];
  const video: Intento[] = [
    { ruta: (id) => `${id}/video_insights`, metrica: tipo === "reel" ? "blue_reels_play_count" : "total_video_views" },
    { ruta: (id) => `${id}/video_insights`, metrica: "total_video_views" },
    { ruta: (id) => `${id}/video_insights`, metrica: "blue_reels_play_count" },
  ];
  const viejas: Intento[] = [
    { ruta: (id) => `${id}/insights`, metrica: "post_video_views" },
    { ruta: (id) => `${id}/insights`, metrica: "post_impressions" },
  ];
  return tipo === "foto" ? [...base, ...viejas] : [...base, ...video, ...viejas];
}

export const INTENTOS_ALCANCE: Intento[] = [
  { ruta: (id) => `${id}/insights`, metrica: "post_total_media_view_unique" },
  { ruta: (id) => `${id}/insights`, metrica: "post_impressions_unique" },
];

/** Saca un número de la respuesta de /insights (valor simple o mapa de valores). */
export function valorInsight(resp: any): number | null {
  const v = resp?.data?.[0]?.values?.[0]?.value ?? resp?.data?.[0]?.total_value?.value;
  if (typeof v === "number" && isFinite(v)) return v;
  if (v && typeof v === "object") {
    const suma = Object.values(v).reduce<number>((a, x) => a + (typeof x === "number" ? x : 0), 0);
    return suma;
  }
  return null;
}

// Códigos de Graph que significan "esto no lo puedes pedir tú" (permiso/token), no "esta métrica no existe".
const CODIGOS_PERMISO = new Set([10, 190, 200, 102, 104]);

export function errorLegible(e: any): { texto: string; codigo: number | null } {
  const codigo = typeof e?.code === "number" ? e.code : null;
  const msg = String(e?.message || "Error de Facebook");
  if (codigo === 190) return { texto: "Token vencido: reconecta la cuenta.", codigo };
  if (codigo === 10 || codigo === 200 || /permission|permiso/i.test(msg)) {
    return { texto: "Falta el permiso read_insights: reconecta la cuenta con Facebook.", codigo };
  }
  return { texto: msg.slice(0, 200), codigo };
}

async function primerValor(
  graph: GraphFn,
  id: string,
  intentos: Intento[]
): Promise<{ valor: number | null; fuente: string | null; error: any | null }> {
  let ultimoError: any = null;
  for (const it of intentos) {
    try {
      const r = await graph(it.ruta(id), { metric: it.metrica, period: "lifetime" });
      const v = valorInsight(r);
      if (v !== null) return { valor: v, fuente: it.metrica, error: null };
    } catch (e: any) {
      ultimoError = e;
      // Si es de permisos/token no tiene sentido probar otra métrica
      if (CODIGOS_PERMISO.has(e?.code)) break;
    }
  }
  return { valor: null, fuente: null, error: ultimoError };
}

export async function metricasDePublicacion(graph: GraphFn, id: string, tipo: TipoContenido): Promise<Metricas> {
  const m: Metricas = { ...VACIAS };

  // 1) Datos "básicos" (no necesitan read_insights): reacciones, comentarios, enlace
  const campos = [
    "permalink_url", "created_time",
    "reactions.summary(total_count).limit(0)",
    "comments.summary(total_count).limit(0)",
    ...(tipo === "foto" ? ["shares"] : []),
  ].join(",");
  try {
    const n = await graph(id, { fields: campos });
    m.permalink = n.permalink_url ? (String(n.permalink_url).startsWith("http") ? n.permalink_url : `https://www.facebook.com${n.permalink_url}`) : null;
    m.publicadoEn = n.created_time || null;
    m.reacciones = n.reactions?.summary?.total_count ?? null;
    m.comentarios = n.comments?.summary?.total_count ?? null;
    m.compartidos = n.shares?.count ?? null;
  } catch (e: any) {
    const { texto, codigo } = errorLegible(e);
    m.error = texto;
    m.codigoError = codigo;
  }

  // 2) Vistas y alcance (cadena de intentos)
  const v = await primerValor(graph, id, intentosVistas(tipo));
  m.vistas = v.valor;
  m.fuente = v.fuente;
  if (v.valor === null && !m.error && v.error) {
    const { texto, codigo } = errorLegible(v.error);
    m.error = texto;
    m.codigoError = codigo;
  }

  // Último recurso para video/reel: el campo "views" del propio nodo
  if (m.vistas === null && tipo !== "foto") {
    try {
      const n = await graph(id, { fields: "views" });
      if (typeof n?.views === "number") { m.vistas = n.views; m.fuente = "views"; }
    } catch { /* ya se reportó el error arriba */ }
  }

  if (m.vistas !== null) {
    const a = await primerValor(graph, id, INTENTOS_ALCANCE);
    m.alcance = a.valor;
    m.error = null; // si logramos leer vistas, un fallo anterior de campos básicos no importa
    m.codigoError = null;
  }
  return m;
}

export interface InfoPagina {
  seguidores: number | null;
  vistas28: number | null;
  error: string | null;
}

export async function infoDePagina(graph: GraphFn, paginaId: string): Promise<InfoPagina> {
  const info: InfoPagina = { seguidores: null, vistas28: null, error: null };
  try {
    const p = await graph(paginaId, { fields: "followers_count,fan_count" });
    info.seguidores = p.followers_count ?? p.fan_count ?? null;
  } catch (e: any) {
    info.error = errorLegible(e).texto;
  }
  for (const metrica of ["page_media_view", "page_impressions"]) {
    try {
      const r = await graph(`${paginaId}/insights`, { metric: metrica, period: "days_28" });
      const vals = r?.data?.[0]?.values;
      const ultimo = Array.isArray(vals) && vals.length ? vals[vals.length - 1]?.value : null;
      if (typeof ultimo === "number") { info.vistas28 = ultimo; break; }
    } catch (e: any) {
      if (CODIGOS_PERMISO.has(e?.code)) { info.error = info.error || errorLegible(e).texto; break; }
    }
  }
  return info;
}

/**
 * Diagnóstico en español de por qué todo está en cero. Devuelve avisos accionables.
 * `filas` son publicaciones con más de 24 h.
 */
export function diagnosticar(filas: { vistas: number | null; error: string | null }[], seguidoresMax: number | null): string[] {
  const avisos: string[] = [];
  if (!filas.length) return avisos;
  const conError = filas.filter((f) => f.error);
  if (conError.length === filas.length) {
    avisos.push(`Facebook no devolvió métricas: ${conError[0].error}`);
    return avisos;
  }
  const leidas = filas.filter((f) => f.vistas !== null);
  if (leidas.length >= 2 && leidas.every((f) => f.vistas === 0)) {
    avisos.push(
      "Todas tus publicaciones (de más de 24 h) tienen 0 vistas. Lo más común: la app de Facebook está en modo DESARROLLO, y entonces los posts solo los ven las personas con rol en la app. Pásala a modo Live (developers.facebook.com → tu app → interruptor arriba) y vuelve a publicar."
    );
    avisos.push("Prueba rápida: abre un post tuyo en una ventana de incógnito. Si no lo puedes ver, es eso.");
  }
  if (seguidoresMax !== null && seguidoresMax < 100) {
    avisos.push("Tus páginas tienen muy pocos seguidores: Facebook casi no da distribución al inicio. Publica a diario y con contenido propio.");
  }
  return avisos;
}

