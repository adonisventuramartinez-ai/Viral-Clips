// Lógica pura (sin red ni base de datos) del cron: qué estado le toca a un post
// tras un intento y cuándo es la siguiente repetición. Separada para poder probarla.

import type { EstadoPost, ResultadoPagina } from "./db";

export const MAX_INTENTOS = 3;
const MIN = 60_000;
const BACKOFF_MS = [5 * MIN, 20 * MIN, 60 * MIN]; // espera tras el intento 1, 2, 3

export interface Decision {
  estado: EstadoPost;
  intentos: number;
  proximaFecha?: string; // solo si vuelve a "pendiente"
  ultimoError: string | null;
}

export function decidir(
  paginasIds: string[],
  resultados: Record<string, ResultadoPagina>,
  intentosPrevios: number,
  ahoraMs: number
): Decision {
  const fallidas = paginasIds.filter((id) => !resultados[id]?.ok);
  if (fallidas.length === 0) return { estado: "completado", intentos: intentosPrevios, ultimoError: null };

  const intentos = intentosPrevios + 1;
  const ultimoError = fallidas
    .map((id) => `${id}: ${resultados[id]?.error || "sin detalle"}`)
    .join(" | ")
    .slice(0, 1000);

  const hayReintentable = fallidas.some((id) => resultados[id]?.reintentable !== false);
  if (!hayReintentable || intentos >= MAX_INTENTOS) {
    return { estado: "error", intentos, ultimoError };
  }
  return {
    estado: "pendiente",
    intentos,
    ultimoError,
    proximaFecha: new Date(ahoraMs + BACKOFF_MS[Math.min(intentos - 1, BACKOFF_MS.length - 1)]).toISOString(),
  };
}

// Siguiente ocurrencia de una serie. Si el cron estuvo caído varios días no
// dispara todo lo atrasado: salta hasta la primera fecha futura.
export function siguienteOcurrencia(
  fechaProgramadaISO: string,
  recurrencia: "ninguna" | "diaria" | "semanal",
  ahoraMs: number
): string | null {
  if (recurrencia === "ninguna") return null;
  const paso = recurrencia === "diaria" ? 86_400_000 : 7 * 86_400_000;
  let proxima = new Date(fechaProgramadaISO).getTime() + paso;
  while (proxima <= ahoraMs) proxima += paso;
  return new Date(proxima).toISOString();
}

