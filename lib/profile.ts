// Reglas de cuentas y perfil. Sin imports a propósito: lo usan la web, las rutas /api y las pruebas.
export const USERNAME_RE = /^[a-z0-9_.]{3,24}$/;                 // mismo patrón que lib/auth.ts (verifySession)
export const AVATAR_RE = /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/;
export const AVATAR_MAX = 150_000;                                // caracteres; una foto de 256 px pesa ~20 000
export const MAX_ACCOUNTS = 20;

/** Usuario en minúsculas (a-z 0-9 _ .), 3 a 24 letras; si no sirve, null. */
export function cleanUsername(v: unknown): string | null {
  const u = typeof v === "string" ? v.trim().toLowerCase().replace(/^@/, "") : "";
  return USERNAME_RE.test(u) ? u : null;
}

/** Nombre para mostrar: 2 a 40 caracteres, sin saltos ni caracteres raros; si no sirve, null. */
export function cleanName(v: unknown): string | null {
  const n = typeof v === "string" ? v.replace(/[\u0000-\u001f\u007f<>]/g, " ").replace(/\s+/g, " ").trim() : "";
  return n.length >= 2 && n.length <= 40 ? n : null;
}

/** Foto: solo imagen en base64 y liviana. */
export function validAvatar(v: unknown): v is string {
  return typeof v === "string" && v.length <= AVATAR_MAX && AVATAR_RE.test(v);
}

export function validPassword(v: unknown): v is string {
  return typeof v === "string" && v.length >= 8 && v.length <= 100;
}

/** Letras para la foto cuando no hay: "Juan Pérez" -> "JP". */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const s = (parts.length > 1 ? parts[0][0] + parts[1][0] : (parts[0] || "?").slice(0, 2)).toUpperCase();
  return s || "?";
}
