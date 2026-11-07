export function fmtTime(sec: number): string {
  const t = Math.floor(sec);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

export const STATUS_LABEL: Record<string, string> = {
  queued: "En cola",
  downloading: "Descargando el video",
  recording: "Grabando",
  transcribing: "Transcribiendo",
  analyzing: "Buscando momentos virales",
  clipping: "Creando clips",
  done: "Listo",
  error: "Error",
  stopped: "Detenido",
};

export const ACTIVE = ["queued", "downloading", "recording", "transcribing", "analyzing", "clipping"];
