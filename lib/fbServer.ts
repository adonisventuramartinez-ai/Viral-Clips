// Publicación en Facebook desde el SERVIDOR (la usa el cron).
// Clave: NO se descarga el archivo en la función. A Facebook se le pasa una URL
// firmada de Supabase (file_url / url) y es Facebook quien lo descarga. Así no
// hay límite de memoria ni de tiempo por el tamaño del video.

import { GRAPH_BASE } from "./graph";

export type TipoPost = "foto" | "video" | "reel";

export interface ParamsPublicar {
  paginaId: string;
  token: string; // token de la página (ya desencriptado)
  tipo: TipoPost;
  urlArchivo: string; // URL firmada, accesible por Facebook
  titulo?: string | null;
  mensaje?: string | null;
}

export interface SalidaPublicar {
  ok: boolean;
  id?: string;
  error?: string;
  reintentable?: boolean;
  codigo?: number;
}

// Códigos de error de Graph que NO tiene sentido reintentar
// 190 token inválido/expirado · 102 sesión · 200 permisos · 10 permiso denegado
// 100 parámetro inválido · 368 bloqueo temporal por política · 506 post duplicado
const CODIGOS_FATALES = new Set([190, 102, 200, 10, 100, 368, 506]);

class FbError extends Error {
  constructor(mensaje: string, public codigo?: number, public reintentable = true) {
    super(mensaje);
  }
}

async function llamar(url: string, init: RequestInit): Promise<any> {
  let res: Response;
  try {
    res = await fetch(url, { ...init, signal: AbortSignal.timeout(30_000) });
  } catch (e: any) {
    throw new FbError(`Sin respuesta de Facebook: ${e.message}`, undefined, true);
  }
  let data: any;
  try {
    data = await res.json();
  } catch {
    throw new FbError(`Respuesta no válida de Facebook (HTTP ${res.status})`, undefined, res.status >= 500);
  }
  if (data?.error) {
    const e = data.error;
    const codigo = typeof e.code === "number" ? e.code : undefined;
    throw new FbError(
      `${e.message || "Error de Facebook"} (código ${codigo ?? "?"}${e.error_subcode ? "/" + e.error_subcode : ""})`,
      codigo,
      codigo === undefined ? true : !CODIGOS_FATALES.has(codigo)
    );
  }
  return data;
}

function formulario(campos: Record<string, string | undefined | null>): URLSearchParams {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(campos)) if (v !== undefined && v !== null && v !== "") p.set(k, v);
  return p;
}

const dormir = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function publicarEnPagina(p: ParamsPublicar): Promise<SalidaPublicar> {
  const texto = [p.titulo, p.mensaje].filter(Boolean).join("\n\n");
  try {
    if (p.tipo === "foto") {
      const d = await llamar(`${GRAPH_BASE}/${p.paginaId}/photos`, {
        method: "POST",
        body: formulario({ access_token: p.token, url: p.urlArchivo, caption: texto, published: "true" }),
      });
      return { ok: true, id: d.post_id || d.id };
    }

    if (p.tipo === "video") {
      const d = await llamar(`${GRAPH_BASE}/${p.paginaId}/videos`, {
        method: "POST",
        body: formulario({
          access_token: p.token,
          file_url: p.urlArchivo,
          description: texto,
          title: p.titulo || undefined,
        }),
      });
      return { ok: true, id: d.id };
    }

    // ----- Reel: API oficial de 3 pasos (start → subir por file_url → finish)
    const inicio = await llamar(`${GRAPH_BASE}/${p.paginaId}/video_reels`, {
      method: "POST",
      body: formulario({ access_token: p.token, upload_phase: "start" }),
    });
    const videoId: string = inicio.video_id;
    const uploadUrl: string = inicio.upload_url;
    if (!videoId || !uploadUrl) throw new FbError("Facebook no devolvió video_id/upload_url para el reel", undefined, true);

    const subida = await llamar(uploadUrl, {
      method: "POST",
      headers: { Authorization: `OAuth ${p.token}`, file_url: p.urlArchivo },
    });
    if (subida?.success === false) throw new FbError("Facebook no pudo descargar el video del reel", undefined, true);

    await llamar(`${GRAPH_BASE}/${p.paginaId}/video_reels`, {
      method: "POST",
      body: formulario({
        access_token: p.token,
        upload_phase: "finish",
        video_id: videoId,
        video_state: "PUBLISHED",
        description: texto,
      }),
    });

    // Procesamiento: unos sondeos cortos. Si sigue "processing" lo damos por
    // enviado (Facebook termina solo); si reporta error, fallamos de verdad.
    for (let i = 0; i < 3; i++) {
      await dormir(5000);
      try {
        const st = await llamar(
          `${GRAPH_BASE}/${videoId}?fields=status&access_token=${encodeURIComponent(p.token)}`,
          { method: "GET" }
        );
        const estado = st?.status?.video_status;
        if (estado === "error") {
          const msg = st?.status?.processing_phase?.errors?.[0]?.message || "Facebook rechazó el reel al procesarlo";
          throw new FbError(msg, undefined, false);
        }
        if (estado === "ready" || estado === "published") break;
      } catch (e) {
        if (e instanceof FbError && e.reintentable === false) throw e;
        break; // si el sondeo falla no invalidamos una publicación ya enviada
      }
    }
    return { ok: true, id: videoId };
  } catch (e: any) {
    return {
      ok: false,
      error: e?.message || "Error desconocido",
      reintentable: e instanceof FbError ? e.reintentable : true,
      codigo: e instanceof FbError ? e.codigo : undefined,
    };
  }
}

