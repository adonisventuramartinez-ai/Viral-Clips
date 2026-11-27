// Estas funciones corren en el NAVEGADOR: las fotos/videos de "Publicar ahora"
// van directo del cliente a Facebook, sin pasar por el límite de tamaño de las
// funciones serverless.

import { GRAPH_BASE, GRAPH_DIALOG, appUrl } from "./graph";
import { supabaseBrowser, BUCKET } from "./supabaseClient";

export interface FacebookPage {
  id: string;
  name: string;
  access_token: string;
  category?: string;
}

export type TipoContenido = "foto" | "video" | "reel";

export interface ValidacionArchivo {
  valido: boolean;
  error?: string;
}

// Límites orientativos de la Graph API (evitan intentar algo que va a fallar).
const LIMITES: Record<TipoContenido, { maxBytes: number; tipos: string[] }> = {
  foto: { maxBytes: 10 * 1024 * 1024, tipos: ["image/jpeg", "image/png", "image/gif", "image/webp"] },
  video: { maxBytes: 1024 * 1024 * 1024 * 4, tipos: ["video/mp4", "video/quicktime", "video/x-msvideo"] },
  reel: { maxBytes: 1024 * 1024 * 1024, tipos: ["video/mp4", "video/quicktime"] },
};

export function validarArchivo(archivo: File, tipo: TipoContenido): ValidacionArchivo {
  const limite = LIMITES[tipo];

  const tipoValido = limite.tipos.some(
    (t) => archivo.type === t || archivo.type.startsWith(t.split("/")[0] + "/")
  );
  if (!tipoValido) {
    return { valido: false, error: `Formato no soportado para ${tipo}. Usa: ${limite.tipos.join(", ")}` };
  }

  if (archivo.size > limite.maxBytes) {
    const maxMb = (limite.maxBytes / (1024 * 1024)).toFixed(0);
    return {
      valido: false,
      error: `El archivo pesa ${(archivo.size / (1024 * 1024)).toFixed(1)}MB, el máximo para ${tipo} es ${maxMb}MB.`,
    };
  }

  return { valido: true };
}

function estadoAleatorio(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getLoginUrl(): string {
  const appId = process.env.NEXT_PUBLIC_FB_APP_ID;
  const redirectUri = `${appUrl(typeof window !== "undefined" ? window.location.origin : "")}/api/fb/auth/callback`;
  // read_insights: necesario para ver vistas/alcance en la pestaña "Métricas"
  const scopes = "pages_manage_posts,pages_read_engagement,pages_show_list,pages_read_user_content,read_insights";
  const state = estadoAleatorio();

  // El servidor compara este state con el que vuelve de Facebook (anti-CSRF)
  if (typeof document !== "undefined") {
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `fb_oauth_state=${state}; Max-Age=600; Path=/; SameSite=Lax${secure}`;
  }

  return (
    `${GRAPH_DIALOG}` +
    `?client_id=${appId}` +
    `&redirect_uri=${encodeURIComponent(redirectUri)}` +
    `&scope=${encodeURIComponent(scopes)}` +
    `&response_type=code` +
    `&state=${state}`
  );
}

export async function obtenerPaginas(userToken: string): Promise<FacebookPage[]> {
  const url = `${GRAPH_BASE}/me/accounts?access_token=${userToken}&fields=id,name,access_token,category&limit=100`;
  const res = await fetch(url);
  const data = await res.json();
  if (data.error) throw new Error(data.error.message || "Error al obtener páginas");
  return data.data || [];
}

/**
 * Publica contenido en una página, reportando progreso de subida (0-100).
 * Usa XMLHttpRequest porque fetch no expone progreso de "upload" de forma
 * estándar en todos los navegadores.
 */
export function publicarContenido(
  pagina: FacebookPage,
  archivo: File,
  tipo: TipoContenido,
  titulo: string,
  mensaje: string,
  onProgress?: (porcentaje: number) => void
): Promise<{ success: boolean; message: string }> {
  if (tipo === "reel") return publicarReel(pagina, archivo, titulo, mensaje, onProgress);

  const textoCompleto = [titulo, mensaje].filter(Boolean).join("\n\n");
  const form = new FormData();
  form.append("access_token", pagina.access_token);

  let endpoint = "";
  if (tipo === "foto") {
    endpoint = `${GRAPH_BASE}/${pagina.id}/photos`;
    form.append("caption", textoCompleto);
    form.append("source", archivo);
  } else {
    endpoint = `${GRAPH_BASE}/${pagina.id}/videos`;
    form.append("description", textoCompleto);
    if (titulo) form.append("title", titulo);
    form.append("source", archivo);
  }

  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", endpoint, true);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (data.error) {
          resolve({ success: false, message: data.error.message || "Error desconocido de Facebook" });
        } else {
          resolve({ success: true, message: `Publicado. ID: ${data.id || data.post_id}` });
        }
      } catch {
        resolve({ success: false, message: "Respuesta inválida de Facebook" });
      }
    };

    xhr.onerror = () => resolve({ success: false, message: "Error de red al subir el archivo" });
    xhr.send(form);
  });
}

// ---------------------------------------------------------------------------
// Reel REAL: el archivo se sube UNA vez a Supabase Storage y el servidor hace el
// flujo oficial de Reels (video_reels) en cada página. Así sale como Reel de verdad.
const rutasSubidas = new WeakMap<File, Promise<string>>();

function subirAStorage(archivo: File): Promise<string> {
  let p = rutasSubidas.get(archivo);
  if (!p) {
    p = (async () => {
      const prep = await fetch("/api/fb/subir-archivo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombreArchivo: archivo.name }),
      }).then((r) => r.json());
      if (prep.error) throw new Error(prep.error);
      const { error } = await supabaseBrowser.storage.from(BUCKET).uploadToSignedUrl(prep.path, prep.token, archivo);
      if (error) throw new Error(error.message);
      return prep.path as string;
    })();
    p.catch(() => rutasSubidas.delete(archivo)); // si falló, el próximo intento vuelve a subir
    rutasSubidas.set(archivo, p);
  }
  return p;
}

async function publicarReel(
  pagina: FacebookPage,
  archivo: File,
  titulo: string,
  mensaje: string,
  onProgress?: (porcentaje: number) => void
): Promise<{ success: boolean; message: string }> {
  try {
    onProgress?.(5);
    const path = await subirAStorage(archivo);
    onProgress?.(60);
    const r = await fetch("/api/fb/reel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paginaId: pagina.id, token: pagina.access_token, path, titulo, mensaje }),
    });
    const d = await r.json();
    onProgress?.(100);
    if (!d.ok) return { success: false, message: d.error || "Facebook rechazó el reel" };
    return { success: true, message: `Reel publicado. ID: ${d.id}` };
  } catch (e: any) {
    return { success: false, message: e?.message || "Error al publicar el reel" };
  }
}

