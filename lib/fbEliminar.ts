// Listar y borrar contenido de una página de Facebook desde el SERVIDOR.
// El token de página nunca sale de aquí.
import { GRAPH_BASE } from "./graph";
import type { ItemFb, TipoContenido } from "./eliminador";

export class ErrorGraph extends Error {
  constructor(mensaje: string, public codigo?: number, public subcodigo?: number) {
    super(mensaje);
  }
}

async function graph(url: string, init: RequestInit = {}): Promise<any> {
  let res: Response;
  try {
    res = await fetch(url, { ...init, signal: AbortSignal.timeout(25_000) });
  } catch (e: any) {
    throw new ErrorGraph(`Sin respuesta de Facebook: ${e.message}`);
  }
  let data: any;
  try {
    data = await res.json();
  } catch {
    throw new ErrorGraph(`Respuesta no válida de Facebook (HTTP ${res.status})`);
  }
  if (data?.error) {
    const e = data.error;
    throw new ErrorGraph(e.message || "Error de Facebook", typeof e.code === "number" ? e.code : undefined, e.error_subcode);
  }
  return data;
}

// Token de la página: se pide con el token de usuario de la cuenta guardada. Si la cuenta no administra
// esa página, no aparece y no se puede tocar nada (así nadie borra en páginas ajenas).
export async function tokenDePagina(tokenUsuario: string, paginaId: string): Promise<{ token: string; nombre: string } | null> {
  let url: string | null =
    `${GRAPH_BASE}/me/accounts?fields=id,name,access_token&limit=100&access_token=${encodeURIComponent(tokenUsuario)}`;
  for (let i = 0; i < 5 && url; i++) {
    const d = await graph(url);
    const p = (d.data || []).find((x: any) => x.id === paginaId);
    if (p?.access_token) return { token: p.access_token, nombre: p.name };
    url = d.paging?.next || null;
  }
  return null;
}

const CAMPOS: Record<TipoContenido, { ruta: string; campos: string; extra: string }> = {
  posts: { ruta: "published_posts", campos: "id,message,created_time,full_picture,permalink_url", extra: "" },
  reels: { ruta: "video_reels", campos: "id,description,created_time,picture,permalink_url,length", extra: "" },
  videos: { ruta: "videos", campos: "id,description,title,created_time,picture,permalink_url,length", extra: "&type=uploaded" },
  fotos: { ruta: "photos", campos: "id,name,created_time,picture,link", extra: "&type=uploaded" },
};

export async function listar(
  token: string, paginaId: string, tipo: TipoContenido, despues?: string, limite = 50
): Promise<{ items: ItemFb[]; siguiente: string | null }> {
  const c = CAMPOS[tipo];
  const url =
    `${GRAPH_BASE}/${paginaId}/${c.ruta}?fields=${c.campos}&limit=${limite}${c.extra}` +
    (despues ? `&after=${encodeURIComponent(despues)}` : "") +
    `&access_token=${encodeURIComponent(token)}`;
  const d = await graph(url);
  const items: ItemFb[] = (d.data || []).map((x: any) => ({
    id: String(x.id),
    texto: String(x.message || x.description || x.name || x.title || "").slice(0, 300),
    fecha: x.created_time || "",
    miniatura: x.full_picture || x.picture || null,
    enlace: x.permalink_url ? (String(x.permalink_url).startsWith("http") ? x.permalink_url : `https://www.facebook.com${x.permalink_url}`) : x.link || null,
    duracion: typeof x.length === "number" ? Math.round(x.length) : null,
  }));
  const siguiente = d.paging?.next ? d.paging?.cursors?.after || null : null;
  return { items, siguiente };
}

// Borra un objeto. Si ya no existe (code 100 / subcode 33) cuenta como borrado: así reintentar es seguro.
export async function borrar(token: string, id: string): Promise<{ ok: boolean; yaNoExistia?: boolean; error?: string; codigo?: number }> {
  try {
    const d = await graph(`${GRAPH_BASE}/${id}`, {
      method: "DELETE",
      body: new URLSearchParams({ access_token: token }),
    });
    if (d?.success === false) return { ok: false, error: "Facebook respondió success=false" };
    return { ok: true };
  } catch (e: any) {
    if (e instanceof ErrorGraph && e.codigo === 100 && e.subcodigo === 33) return { ok: true, yaNoExistia: true };
    return { ok: false, error: e?.message || "Error desconocido", codigo: e instanceof ErrorGraph ? e.codigo : undefined };
  }
}

