import crypto from "crypto";

// ENCRYPTION_KEY debe ser un string hex de 64 caracteres (32 bytes).
// Generar con: openssl rand -hex 32
function getKey(): Buffer {
  const hex = (process.env.ENCRYPTION_KEY || "").trim();
  if (!hex || hex.length !== 64) {
    throw new Error("ENCRYPTION_KEY debe ser un hex de 64 caracteres (32 bytes). Revisa tus variables de entorno.");
  }
  return Buffer.from(hex, "hex");
}

export function encriptar(texto: string): string {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", getKey(), iv);
  const encriptado = Buffer.concat([cipher.update(texto, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();
  // formato: iv:authTag:ciphertext (todo en base64)
  return [iv.toString("base64"), authTag.toString("base64"), encriptado.toString("base64")].join(":");
}

export function desencriptar(payload: string): string {
  const [ivB64, authTagB64, dataB64] = payload.split(":");
  const iv = Buffer.from(ivB64, "base64");
  const authTag = Buffer.from(authTagB64, "base64");
  const data = Buffer.from(dataB64, "base64");
  const decipher = crypto.createDecipheriv("aes-256-gcm", getKey(), iv);
  decipher.setAuthTag(authTag);
  const descifrado = Buffer.concat([decipher.update(data), decipher.final()]);
  return descifrado.toString("utf8");
}

