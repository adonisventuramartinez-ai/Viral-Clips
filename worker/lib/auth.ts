// Token de sesión = SHA-256 de la contraseña (Web Crypto, funciona en middleware y en rutas /api).
export async function authToken(password: string): Promise<string> {
  const data = new TextEncoder().encode("clipforge:" + password);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
