// Etiquetas, colores y utilidades compartidas por Cola, Calendario e Inicio.
export const ETIQUETA_ESTADO: Record<string, string> = {
  pendiente: "Pendiente",
  publicando: "Publicando",
  completado: "Publicado",
  error: "Error",
  cancelado: "Cancelado",
};

export const COLOR_ESTADO: Record<string, string> = {
  pendiente: "#f59e0b",
  publicando: "#38bdf8",
  completado: "#22c55e",
  error: "#ef4444",
  cancelado: "#6b7280",
};

export const ICONO_TIPO: Record<string, string> = { foto: "🖼️", video: "🎬", reel: "🎞️" };

export function tiempoRelativo(iso: string, ahoraMs: number = Date.now()): string {
  const diff = new Date(iso).getTime() - ahoraMs;
  const abs = Math.abs(diff);
  const min = Math.floor(abs / 60_000);
  const h = Math.floor(min / 60);
  const d = Math.floor(h / 24);
  const txt = d > 0 ? `${d}d ${h % 24}h` : h > 0 ? `${h}h ${min % 60}m` : `${min}m`;
  return diff >= 0 ? `en ${txt}` : `hace ${txt}`;
}

