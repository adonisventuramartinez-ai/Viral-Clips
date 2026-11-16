import { createHash, randomBytes, scrypt as _scrypt, timingSafeEqual } from "node:crypto";

// Contraseñas de cuenta: scrypt con sal propia. Formato guardado: "scrypt$<sal hex>$<hash hex>". Solo para rutas /api (Node).
function scrypt(pw: string, salt: Buffer): Promise<Buffer> {
  return new Promise((res, rej) => _scrypt(pw.normalize("NFKC"), salt, 64, { N: 16384, r: 8, p: 1 }, (e, k) => (e ? rej(e) : res(k))));
}

export async function hashPassword(pw: string): Promise<string> {
  const salt = randomBytes(16);
  return `scrypt$${salt.toString("hex")}$${(await scrypt(pw, salt)).toString("hex")}`;
}

export async function checkPassword(pw: string, stored: string | null | undefined): Promise<boolean> {
  // Aunque no exista el usuario se hace el mismo trabajo, para que no se note por el tiempo.
  const parts = (stored || "scrypt$00000000000000000000000000000000$" + "0".repeat(128)).split("$");
  if (parts.length !== 3 || parts[0] !== "scrypt") return false;
  const salt = Buffer.from(parts[1], "hex"), want = Buffer.from(parts[2], "hex");
  const got = await scrypt(pw, salt);
  return !!stored && want.length === got.length && timingSafeEqual(want, got);
}

/** Compara dos textos secretos en tiempo constante (se comparan sus hashes, que miden lo mismo siempre). */
export function sameSecret(a: string, b: string): boolean {
  return timingSafeEqual(createHash("sha256").update(a).digest(), createHash("sha256").update(b).digest());
}
