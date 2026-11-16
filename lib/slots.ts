// Mejores horas para publicar. Espejo de worker/viral.py (next_slots): mismos valores por defecto y misma lógica.
// Variables opcionales en Vercel: POST_SLOTS="12:30,19:00,21:30", POST_TZ_OFFSET="-4", POST_MIN_GAP_MIN="90", POST_MAX_PER_DAY="6".

// `learned` = horas aprendidas en Mi página (tabla best_hours); si viene vacío se usan las de POST_SLOTS.
export function nextSlot(taken: string[], now = new Date(), learned: string[] = []): Date | null {
  const slots = (learned.length ? learned.join(",") : process.env.POST_SLOTS || "12:30,19:00,21:30").split(",").map((s) => s.trim()).filter(Boolean)
    .map((s) => s.split(":").map(Number)).filter(([h, m]) => Number.isFinite(h) && Number.isFinite(m)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (!slots.length) return null;
  const off = Number(process.env.POST_TZ_OFFSET ?? -4);
  const gap = Number(process.env.POST_MIN_GAP_MIN || 90) * 60_000;
  const cap = Number(process.env.POST_MAX_PER_DAY || 6);
  const busy = taken.map((t) => Date.parse(t)).filter(Number.isFinite);
  const dayKey = (ms: number) => new Date(ms + off * 3_600_000).toISOString().slice(0, 10);
  const local = new Date(now.getTime() + off * 3_600_000);
  for (let d = 0; d < 90; d++) {
    for (const [h, m] of slots) {
      const cand = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate() + d, h, m) - off * 3_600_000;
      if (cand <= now.getTime() + 2 * 60_000) continue;
      if (busy.some((b) => Math.abs(cand - b) < gap)) continue;
      if (busy.filter((b) => dayKey(b) === dayKey(cand)).length >= cap) continue;
      return new Date(cand);
    }
  }
  return null;
}
