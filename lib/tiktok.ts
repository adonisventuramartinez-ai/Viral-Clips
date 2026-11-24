// Clasifica lo que el usuario pega: enlace de video (TikTok o Instagram), enlace corto o perfil de TikTok (@usuario).
// Solo se aceptan dominios de TikTok e Instagram (evita que se use la app para descargar de cualquier sitio).

export type Plataforma = "tiktok" | "instagram";

export interface EntradaTikTok {
  tipo: "video" | "perfil";
  url: string;
  plataforma: Plataforma;
}

const HOST_TIKTOK = /^(www\.|m\.|vm\.|vt\.)?tiktok\.com$/i;
const HOST_INSTAGRAM = /^(www\.|m\.)?instagram\.com$|^instagr\.am$/i;
const USUARIO = /^@[A-Za-z0-9_.]{2,24}$/;
const CODIGO_IG = /^[A-Za-z0-9_-]{5,40}$/;

function instagram(u: URL): EntradaTikTok | null {
  const partes = u.pathname.split("/").filter(Boolean);
  // /reel/CODE · /reels/CODE · /p/CODE · /tv/CODE · /share/reel/CODE · /share/p/CODE · /usuario/reel/CODE · /usuario/p/CODE
  let i = 0;
  if (partes[0] === "share") i = 1;
  else if (partes.length >= 3 && !["reel", "reels", "p", "tv"].includes(partes[0])) i = 1; // salta el nombre de usuario
  const clase = partes[i];
  const codigo = partes[i + 1];
  if (!["reel", "reels", "p", "tv"].includes(clase) || !codigo || !CODIGO_IG.test(codigo)) return null;
  if (partes.length > i + 2) return null;
  const ruta = partes[0] === "share" ? `share/${clase}` : clase === "reels" ? "reel" : clase;
  return { tipo: "video", plataforma: "instagram", url: `https://www.instagram.com/${ruta}/${codigo}/` };
}

export function clasificarEntrada(crudo: string): EntradaTikTok | null {
  const texto = (crudo || "").trim();
  if (!texto || texto.length > 300) return null;

  if (USUARIO.test(texto)) return { tipo: "perfil", plataforma: "tiktok", url: `https://www.tiktok.com/${texto}` };

  let u: URL;
  try {
    u = new URL(/^https?:\/\//i.test(texto) ? texto : `https://${texto}`);
  } catch {
    return null;
  }
  if (u.protocol !== "https:" && u.protocol !== "http:") return null;
  if (HOST_INSTAGRAM.test(u.hostname)) return instagram(u);
  if (!HOST_TIKTOK.test(u.hostname)) return null;

  const host = u.hostname.toLowerCase();
  const partes = u.pathname.split("/").filter(Boolean);

  // Enlaces cortos: vm.tiktok.com/XXXX, vt.tiktok.com/XXXX, tiktok.com/t/XXXX
  if (host.startsWith("vm.") || host.startsWith("vt.") || partes[0] === "t") {
    if (!partes.length) return null;
    return { tipo: "video", plataforma: "tiktok", url: `https://${host}${u.pathname}` };
  }

  // https://www.tiktok.com/@usuario/video/123456789
  if (partes.length >= 3 && USUARIO.test(partes[0]) && partes[1] === "video" && /^\d{8,25}$/.test(partes[2])) {
    return { tipo: "video", plataforma: "tiktok", url: `https://www.tiktok.com/${partes[0]}/video/${partes[2]}` };
  }

  // https://www.tiktok.com/@usuario
  if (partes.length === 1 && USUARIO.test(partes[0])) {
    return { tipo: "perfil", plataforma: "tiktok", url: `https://www.tiktok.com/${partes[0]}` };
  }
  return null;
}

