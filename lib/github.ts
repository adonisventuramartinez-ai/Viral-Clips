// Despierta el worker de GitHub Actions (workflow_dispatch). El worker procesa TODAS
// las importaciones pendientes, así que no hace falta pasarle datos.

import { limpiarEnv, repoGithub } from "./env";

export interface ConfigGithub {
  token: string;
  repo: string; // "usuario/repositorio"
  workflow: string;
  rama: string;
}

// Lee y normaliza GITHUB_TOKEN / GITHUB_REPO / GITHUB_WORKFLOW / GITHUB_BRANCH
// (acepta el repo como URL completa, con .git, con espacios, etc.).
export function configGithub(): ConfigGithub {
  return {
    token: limpiarEnv(process.env.GITHUB_TOKEN),
    repo: repoGithub(process.env.GITHUB_REPO),
    workflow: limpiarEnv(process.env.GITHUB_WORKFLOW) || "tiktok.yml",
    rama: limpiarEnv(process.env.GITHUB_BRANCH) || "main",
  };
}

export async function despacharWorker(): Promise<{ ok: boolean; error?: string }> {
  const { token, repo, workflow, rama: ref } = configGithub();
  if (!token || !repo) {
    return { ok: false, error: "Falta GITHUB_TOKEN o GITHUB_REPO en las variables de Vercel" };
  }
  if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) {
    return { ok: false, error: `GITHUB_REPO debe tener la forma usuario/repositorio (ahora vale "${repo.slice(0, 60)}")` };
  }
  try {
    const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fb-web-publisher",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref }),
      signal: AbortSignal.timeout(15_000),
    });
    if (r.status === 204) return { ok: true };
    const detalle = (await r.text().catch(() => "")).slice(0, 200);
    const pista =
      r.status === 404
        ? ` (¿existe .github/workflows/${workflow} en la RAÍZ del repositorio, en la rama ${ref}, y el token tiene acceso a ${repo}?)`
        : r.status === 422
        ? ` (la rama "${ref}" no existe en ${repo}, o ${workflow} no tiene "workflow_dispatch": revisa GITHUB_BRANCH)`
        : r.status === 401 || r.status === 403
        ? " (revisa el GITHUB_TOKEN: caducado, o sin permiso Actions → Read and write sobre ese repositorio)"
        : "";
    return { ok: false, error: `GitHub respondió ${r.status}${pista} ${detalle}`.trim() };
  } catch (e: any) {
    return { ok: false, error: `No se pudo contactar a GitHub: ${e.message}` };
  }
}

