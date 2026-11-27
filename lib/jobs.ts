// Ayudas para encolar trabajos con prioridad. Si aún no corriste 0008_cola.sql (columna "priority"), se encola igual sin ella.
export const PRIORITY = { record: 10, clip: 5, transform: 5, text_to_video: 3, search: 2, download: 0 } as const;

export async function insertJob(db: any, row: Record<string, unknown>, type: keyof typeof PRIORITY) {
  const res = await db.from("jobs").insert({ ...row, type, priority: PRIORITY[type] });
  if (res.error && /priority/i.test(res.error.message)) return db.from("jobs").insert({ ...row, type });
  return res;
}
