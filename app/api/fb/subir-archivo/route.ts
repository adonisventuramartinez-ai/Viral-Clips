import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { supabaseAdmin, BUCKET } from "@/lib/db";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

const EXTENSIONES = new Set(["jpg", "jpeg", "png", "gif", "webp", "mp4", "mov"]);

// El navegador nunca sube el archivo a través de esta función (evita el límite
// de tamaño de Vercel): solo pide "permiso" aquí y sube directo a Supabase
// Storage. El archivo queda dentro de una carpeta con el id del dueño.
export async function POST(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  try {
    const { nombreArchivo } = await req.json();
    if (!nombreArchivo || typeof nombreArchivo !== "string") {
      return NextResponse.json({ error: "Falta nombreArchivo" }, { status: 400 });
    }

    const extension = (nombreArchivo.split(".").pop() || "").toLowerCase();
    if (!EXTENSIONES.has(extension)) {
      return NextResponse.json(
        { error: `Extensión no permitida (.${extension}). Usa: ${[...EXTENSIONES].join(", ")}` },
        { status: 400 }
      );
    }

    const path = `${sesion.sub}/${Date.now()}-${crypto.randomBytes(6).toString("hex")}.${extension}`;
    const { data, error } = await supabaseAdmin.storage.from(BUCKET).createSignedUploadUrl(path);
    if (error) throw error;

    return NextResponse.json({ path: data.path, token: data.token });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al preparar la subida" }, { status: 500 });
  }
}

