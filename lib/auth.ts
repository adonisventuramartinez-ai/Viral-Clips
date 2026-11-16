// Token de sesión = SHA-256 de la contraseña (Web Crypto, funciona en middleware y en rutas /api).
export async function authToken(password: string): Promise<string> {
  const data = new TextEncoder().encode("clipforge:" + password);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ---------------------------------------------------------------------------------------------------------
// Parte 13: sesiones de cuenta (usuario + contraseña). Cookie "cf_session" = usuario-vence-firma.
// La firma es un HMAC con la clave de acceso (APP_PASSWORD): si cambias APP_PASSWORD, todas las sesiones se cierran.
// El usuario solo lleva a-z 0-9 _ . (nunca "-"), así que "-" separa las partes sin confusión.
const enc = new TextEncoder();

export const SESSION_DAYS = 30;
const USERNAME_RE = /^[a-z0-9_.]{3,24}$/;   // mismo patrón que lib/profile.ts

/** Clave con la que se firman las sesiones. En producción siempre hay APP_PASSWORD (el middleware lo exige). */
export function sessionSecret(): string {
  return process.env.APP_PASSWORD || "clipforge-dev-sin-clave";
}

async function hmacHex(secret: string, msg: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode("clipforge-session:" + secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(msg));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sameText(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export async function signSession(username: string, secret: string, days = SESSION_DAYS, nowMs = Date.now()): Promise<string> {
  const exp = Math.floor(nowMs / 1000) + days * 86400;
  return `${username}-${exp}-${await hmacHex(secret, `${username}|${exp}`)}`;
}

/** Devuelve el usuario si la cookie es válida y no venció; si no, null. */
export async function verifySession(token: string | undefined | null, secret: string, nowMs = Date.now()): Promise<string | null> {
  if (!token || token.length > 200) return null;
  const i = token.lastIndexOf("-");
  const j = token.lastIndexOf("-", i - 1);
  if (i < 0 || j < 0) return null;
  const username = token.slice(0, j), exp = token.slice(j + 1, i), sig = token.slice(i + 1);
  if (!USERNAME_RE.test(username) || !/^\d{1,12}$/.test(exp)) return null;
  if (Number(exp) * 1000 < nowMs) return null;
  return sameText(sig, await hmacHex(secret, `${username}|${exp}`)) ? username : null;
}
