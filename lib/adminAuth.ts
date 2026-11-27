import { NextRequest } from "next/server";
import crypto from "crypto";

function firmar(valor: string): string {
  const key = process.env.ENCRYPTION_KEY || "";
  return crypto.createHmac("sha256", key).update(valor).digest("hex");
}

export function esAdminValido(req: NextRequest): boolean {
  const cookie = req.cookies.get("admin_session")?.value;
  if (!cookie) return false;
  const [valor, firma] = cookie.split(".");
  if (!valor || !firma) return false;
  return firmar(valor) === firma;
}

