import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin, BUCKET } from "@/lib/db";
import { adminDe, noAutorizado } from "@/lib/fbAuth";
import { GRAPH_BASE, fbAppId, fbAppSecret } from "@/lib/graph";
import { configGithub } from "@/lib/github";
import { limpiarEnv, tipoLlaveSupabase, esLlaveSecreta, urlSupabase } from "@/lib/env";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

type Nivel = "ok" | "aviso" | "error";
interface Chequeo {
  id: string;
  titulo: string;
  nivel: Nivel;
  detalle: string;
}

const hay = (n: string) => !!limpiarEnv(process.env[n]);

// Autodiagnóstico: en vez de descubrir un problema de configuración cuando una
// publicación falla a las 3 a. m., aquí se ve todo de un vistazo.
export async function GET(req: NextRequest) {
  if (!(await adminDe(req))) return noAutorizado();

  const c: Chequeo[] = [];
  const add = (id: string, titulo: string, nivel: Nivel, detalle: string) => c.push({ id, titulo, nivel, detalle });

  // ---- Variables de entorno
  const obligatorias = [
    "FB_APP_ID", "FB_APP_SECRET", "NEXT_PUBLIC_FB_APP_ID",
    "SUPABASE_URL", "SUPABASE_SECRET_KEY", "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "ENCRYPTION_KEY", "CRON_SECRET", "ADMIN_PASSWORD",
  ];
  const alternativas: Record<string, string> = {
    SUPABASE_URL: "NEXT_PUBLIC_SUPABASE_URL",
    SUPABASE_SECRET_KEY: "SUPABASE_SERVICE_ROLE_KEY",
    NEXT_PUBLIC_SUPABASE_ANON_KEY: "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  };
  const faltan = obligatorias.filter((n) => !hay(n) && !(alternativas[n] && hay(alternativas[n])));
  add("env", "Variables de entorno", faltan.length ? "error" : "ok", faltan.length ? `Faltan: ${faltan.join(", ")}` : "Todas las obligatorias están definidas");

  const clave = (process.env.ENCRYPTION_KEY || "").trim();

  // ---- Supabase: ¿la llave "secreta" es de verdad la secreta? ¿y las dos URLs son del mismo proyecto?
  const llaveSecreta = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (llaveSecreta) {
    const tipo = tipoLlaveSupabase(llaveSecreta);
    add("llave", "Llave secreta de Supabase", esLlaveSecreta(tipo) ? "ok" : tipo === "desconocida" ? "aviso" : "error",
      esLlaveSecreta(tipo)
        ? `Correcta (${tipo})`
        : tipo === "desconocida"
        ? "No se reconoce el formato (esperado sb_secret_… o un JWT service_role). Si las tablas de abajo responden bien, ignora este aviso."
        : `SUPABASE_SECRET_KEY contiene la llave PÚBLICA (${tipo}). Pon la SECRETA: Supabase → Project Settings → API Keys. Esa misma va en el secret SUPABASE_SERVICE_KEY de GitHub.`);
  }
  const urlServidor = urlSupabase(process.env.SUPABASE_URL);
  const urlNavegador = urlSupabase(process.env.NEXT_PUBLIC_SUPABASE_URL);
  if (urlServidor && urlNavegador && urlServidor !== urlNavegador) {
    add("urls", "URL de Supabase", "error", `SUPABASE_URL (${urlServidor}) y NEXT_PUBLIC_SUPABASE_URL (${urlNavegador}) apuntan a proyectos distintos. Deben ser iguales.`);
  }
  if (hay("FB_APP_ID") && hay("NEXT_PUBLIC_FB_APP_ID") && fbAppId() !== limpiarEnv(process.env.NEXT_PUBLIC_FB_APP_ID)) {
    add("fbids", "App ID de Facebook", "error", "FB_APP_ID y NEXT_PUBLIC_FB_APP_ID son distintos: el login fallará con \"token de otra app\".");
  }
  add("clave", "ENCRYPTION_KEY", /^[0-9a-fA-F]{64}$/.test(clave) ? "ok" : "error",
    /^[0-9a-fA-F]{64}$/.test(clave) ? "Formato correcto (64 hex)" : "Debe ser hex de 64 caracteres (openssl rand -hex 32). Si la cambias, los tokens ya guardados dejan de funcionar.");
  if (!hay("SESSION_SECRET")) add("sesion", "SESSION_SECRET", "aviso", "No definido: las sesiones se firman con ENCRYPTION_KEY. Mejor usar un secreto distinto (openssl rand -hex 32).");
  if (!hay("NEXT_PUBLIC_APP_URL")) add("url", "NEXT_PUBLIC_APP_URL", "aviso", "No definido: se usa el dominio de cada petición. Defínelo con tu dominio final para que el login de Facebook no falle en previews.");

  // ---- Base de datos: tablas y columnas de la migración 005
  const comprobaciones: [string, string, string][] = [
    ["usuarios_autorizados", "fb_id", "Tabla usuarios_autorizados"],
    ["cuentas_fb", "token_invalido_en", "Tabla cuentas_fb (+ token_invalido_en)"],
    ["posts_programados", "fecha_original", "Tabla posts_programados (+ fecha_original)"],
    ["plantillas", "id", "Tabla plantillas"],
    ["importaciones", "id", "Tabla importaciones"],
    ["cron_latido", "ultima_limpieza", "Tabla cron_latido (+ ultima_limpieza)"],
    ["rate_limit", "clave", "Tabla rate_limit"],
  ];
  const faltantesDb: string[] = [];
  for (const [tabla, col, etiqueta] of comprobaciones) {
    try {
      const { error } = await supabaseAdmin.from(tabla).select(col).limit(1);
      if (error) faltantesDb.push(etiqueta);
    } catch {
      faltantesDb.push(etiqueta);
    }
  }
  add("db", "Base de datos", faltantesDb.length ? "error" : "ok",
    faltantesDb.length ? `Falta o falla: ${faltantesDb.join("; ")}. Ejecuta supabase/migrations/005_esquema_completo_y_automatizacion.sql` : "Todas las tablas y columnas existen");

  try {
    const { data, error } = await supabaseAdmin.rpc("rl_hit", { p_clave: "diagnostico", p_max: 1_000_000, p_ventana_seg: 60 });
    add("rl", "Límite de intentos (rl_hit)", !error && data === true ? "ok" : "aviso",
      !error && data === true ? "Función disponible" : "La función rl_hit no existe: el login no tiene freno anti fuerza bruta (migración 005)");
  } catch {
    add("rl", "Límite de intentos (rl_hit)", "aviso", "No se pudo comprobar");
  }

  // ---- Storage
  try {
    const { data, error } = await supabaseAdmin.storage.getBucket(BUCKET);
    if (error || !data) add("bucket", "Bucket de archivos", "error", `No existe el bucket "${BUCKET}" (migración 005 o créalo en Storage)`);
    else add("bucket", "Bucket de archivos", data.public ? "error" : "ok",
      data.public ? "El bucket es PÚBLICO: cualquiera con la URL puede ver tus videos. Ponlo privado (migración 005)." : "Existe y es privado");
  } catch (e: any) {
    add("bucket", "Bucket de archivos", "error", e?.message || "No se pudo comprobar");
  }

  // ---- Cron
  try {
    const { data } = await supabaseAdmin.from("cron_latido").select("ultimo, procesados, ultima_limpieza").eq("id", 1).maybeSingle();
    if (!data?.ultimo) add("cron", "Cron", "error", "Nunca se ha ejecutado. Configura cron-job.org o la migración 006 (pg_cron) apuntando a /api/cron.");
    else {
      const seg = Math.round((Date.now() - new Date(data.ultimo).getTime()) / 1000);
      add("cron", "Cron", seg <= 150 ? "ok" : seg <= 600 ? "aviso" : "error",
        seg <= 150 ? `Última ejecución hace ${seg} s` : `Última ejecución hace ${Math.round(seg / 60)} min: no está corriendo cada minuto`);
    }
    if (process.env.LIMPIEZA_STORAGE === "off") add("limpieza", "Limpieza de Storage", "aviso", "Desactivada (LIMPIEZA_STORAGE=off)");
    else add("limpieza", "Limpieza de Storage", data?.ultima_limpieza ? "ok" : "aviso",
      data?.ultima_limpieza ? `Última limpieza: ${new Date(data.ultima_limpieza).toLocaleString("es")}` : "Aún no ha corrido (se ejecuta sola cada 6 h desde el cron)");
  } catch {
    add("cron", "Cron", "error", "No se pudo leer cron_latido");
  }

  // ---- Facebook: ¿el App ID + Secret son válidos?
  try {
    if (hay("FB_APP_ID") && hay("FB_APP_SECRET")) {
      const r = await fetch(`${GRAPH_BASE}/${fbAppId()}?access_token=${encodeURIComponent(`${fbAppId()}|${fbAppSecret()}`)}`, {
        signal: AbortSignal.timeout(10_000),
      });
      const d = await r.json();
      add("fb", "App de Facebook", d?.id ? "ok" : "error", d?.id ? `App "${d.name || d.id}" responde` : `Facebook rechazó el App ID/Secret: ${d?.error?.message || "sin detalle"}`);
    }
  } catch (e: any) {
    add("fb", "App de Facebook", "aviso", `No se pudo contactar a Facebook: ${e?.message}`);
  }

  // ---- Cuentas con token vencido
  try {
    const { data, error } = await supabaseAdmin.from("cuentas_fb").select("nombre").not("token_invalido_en", "is", null);
    if (!error && data?.length) add("tokens", "Cuentas de Facebook", "aviso", `Necesitan reconectarse (token vencido): ${data.map((x: any) => x.nombre).join(", ")}`);
    else if (!error) add("tokens", "Cuentas de Facebook", "ok", "Ninguna con token vencido");
  } catch {}

  // ---- GitHub (worker de TikTok): opcional
  if (hay("GITHUB_TOKEN") || hay("GITHUB_REPO")) {
    const gh = configGithub();
    const cab = { Authorization: `Bearer ${gh.token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "fb-web-publisher" };
    if (!gh.token || !gh.repo) {
      add("github", "Worker de TikTok (GitHub)", "error", "Falta GITHUB_TOKEN o GITHUB_REPO (necesitas las dos).");
    } else if (!/^[\w.-]+\/[\w.-]+$/.test(gh.repo)) {
      add("github", "Worker de TikTok (GitHub)", "error", `GITHUB_REPO debe ser usuario/repositorio (ahora: "${gh.repo.slice(0, 60)}").`);
    } else {
      try {
        // 1) ¿el token ve el repo y existe la rama configurada?
        const rRepo = await fetch(`https://api.github.com/repos/${gh.repo}`, { headers: cab, signal: AbortSignal.timeout(10_000) });
        if (!rRepo.ok) {
          add("github", "Worker de TikTok (GitHub)", "error",
            `GitHub respondió ${rRepo.status} al abrir ${gh.repo}: ${rRepo.status === 401 ? "GITHUB_TOKEN inválido o caducado" : "el token no tiene acceso a ese repositorio (o el nombre está mal escrito)"}.`);
        } else {
          const repo = await rRepo.json();
          if (repo.default_branch && repo.default_branch !== gh.rama) {
            add("github-rama", "Rama del worker", "error", `El repositorio usa la rama "${repo.default_branch}" pero GITHUB_BRANCH vale "${gh.rama}": el despacho dará error 422/404. Pon GITHUB_BRANCH=${repo.default_branch}.`);
          }
          // 2) ¿existe el workflow (en la raíz del repo) y es válido?
          const rWf = await fetch(`https://api.github.com/repos/${gh.repo}/actions/workflows/${encodeURIComponent(gh.workflow)}`, { headers: cab, signal: AbortSignal.timeout(10_000) });
          if (!rWf.ok) {
            add("github", "Worker de TikTok (GitHub)", "error", `No se encontró .github/workflows/${gh.workflow} en ${gh.repo} (HTTP ${rWf.status}). Debe estar en la RAÍZ del repositorio, no dentro de otra carpeta. ${rWf.status === 403 ? "Además el token necesita Actions: Read and write." : ""}`.trim());
          } else {
            const wf = await rWf.json();
            if (wf.state && wf.state !== "active") {
              add("github", "Worker de TikTok (GitHub)", "error", `El workflow está en estado "${wf.state}" (GitHub desactiva los programados tras 60 días sin actividad). Actívalo en la pestaña Actions del repo.`);
            } else {
              // 3) Última ejecución: aquí se ve si el worker corre y si falla
              const rRuns = await fetch(`https://api.github.com/repos/${gh.repo}/actions/workflows/${encodeURIComponent(gh.workflow)}/runs?per_page=1`, { headers: cab, signal: AbortSignal.timeout(10_000) });
              const runs = rRuns.ok ? (await rRuns.json())?.workflow_runs || [] : [];
              if (!runs.length) {
                add("github", "Worker de TikTok (GitHub)", "aviso", "Token y workflow accesibles, pero el worker aún no se ha ejecutado nunca. Importa un enlace o ejecútalo a mano en Actions.");
              } else {
                const u = runs[0];
                const min = Math.round((Date.now() - new Date(u.created_at).getTime()) / 60_000);
                const falla = u.status === "completed" && !["success", "skipped", "cancelled"].includes(u.conclusion);
                add("github", "Worker de TikTok (GitHub)", falla ? "error" : "ok",
                  falla ? `La última ejecución (hace ${min} min) terminó en "${u.conclusion}". Ábrela para ver el motivo: ${u.html_url}` : `Token y workflow correctos. Última ejecución hace ${min} min (${u.status === "completed" ? u.conclusion : u.status}).`);
              }
            }
          }
        }
      } catch (e: any) {
        add("github", "Worker de TikTok (GitHub)", "aviso", `No se pudo contactar a GitHub: ${e?.message}`);
      }
    }

    // 4) ¿Hay enlaces esperando demasiado? (el worker no está procesando)
    try {
      const { data } = await supabaseAdmin
        .from("importaciones")
        .select("creado_en")
        .eq("estado", "pendiente")
        .order("creado_en", { ascending: true })
        .limit(1);
      if (data?.length) {
        const min = Math.round((Date.now() - new Date(data[0].creado_en).getTime()) / 60_000);
        if (min >= 10) add("cola-tiktok", "Cola de TikTok", "error", `Hay importaciones esperando desde hace ${min} min: el worker no las está procesando. Revisa el resultado de GitHub → Actions y que los secrets SUPABASE_URL / SUPABASE_SERVICE_KEY existan en el repo.`);
      }
    } catch {}
  } else {
    add("github", "Worker de TikTok (GitHub)", "aviso", "No configurado (GITHUB_TOKEN / GITHUB_REPO): la pestaña TikTok no podrá importar. Si no la usas, ignóralo.");
  }

  const resumen: Nivel = c.some((x) => x.nivel === "error") ? "error" : c.some((x) => x.nivel === "aviso") ? "aviso" : "ok";
  return NextResponse.json({ resumen, chequeos: c });
}

