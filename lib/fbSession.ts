// Sesiones firmadas con HMAC-SHA256 (Web Crypto: funciona en el middleware y
// en las rutas de Node). El token lleva fecha de expiración DENTRO de la firma,
// así que no depende de que el navegador respete el maxAge de la cookie.

export const COOKIE_USUARIO = "sesion";
export const COOKIE_ADMIN = "admin_session";

export interface Sesion {
  sub: string; // fb_id del usuario (o "admin")
  nombre: string;
  rol: "usuario" | "admin";
  exp: number; // segundos unix
}

const enc = new TextEncoder();
const dec = new TextDecoder();

function secreto(): string {
  const s = process.env.SESSION_SECRET || process.env.ENCRYPTION_KEY;
  if (!s || s.length < 32) {
    throw new Error("Falta SESSION_SECRET (o ENCRYPTION_KEY) de al menos 32 caracteres.");
  }
  return s;
}

function aB64Url(bytes: Uint8Array): string {
  let s = "";
  bytes.forEach((b) => (s += String.fromCharCode(b)));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function deB64Url(str: string): Uint8Array {
  const b64 = str.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (str.length % 4)) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function llave(): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    enc.encode("sesion-v1:" + secreto()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

export async function firmarSesion(datos: Omit<Sesion, "exp">, ttlSegundos: number): Promise<string> {
  const payload = aB64Url(
    enc.encode(JSON.stringify({ ...datos, exp: Math.floor(Date.now() / 1000) + ttlSegundos }))
  );
  const firma = await crypto.subtle.sign("HMAC", await llave(), enc.encode(payload) as unknown as BufferSource);
  return `${payload}.${aB64Url(new Uint8Array(firma))}`;
}

export async function verificarSesion(token?: string | null): Promise<Sesion | null> {
  if (!token) return null;
  const [payload, firma] = token.split(".");
  if (!payload || !firma) return null;
  try {
    // crypto.subtle.verify compara en tiempo constante
    const ok = await crypto.subtle.verify("HMAC", await llave(), deB64Url(firma) as unknown as BufferSource, enc.encode(payload));
    if (!ok) return null;
    const datos = JSON.parse(dec.decode(deB64Url(payload))) as Sesion;
    if (!datos.exp || datos.exp < Math.floor(Date.now() / 1000)) return null;
    if (datos.rol !== "usuario" && datos.rol !== "admin") return null;
    return datos;
  } catch {
    return null;
  }
}
