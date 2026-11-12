export type Clip = {
  id: string;
  title: string;
  start: string; // "3:10"
  end: string;
  score: number; // 0-100 probabilidad viral
  sizeMb: number;
  seconds?: number;
  path?: string;
  startSec?: number;
  endSec?: number;
  captions: string; // solo demo: texto superpuesto
  thumb: string; // solo demo: gradiente
  videoUrl?: string; // clips reales: URL firmada de Supabase Storage
  downloadUrl?: string;
  reason?: string;
  isPublic?: boolean;
  description?: string;
  hashtags?: string[];
};

export type SourceRow = {
  id: string;
  title: string | null;
  url: string | null;
  status: string;
  error: string | null;
  created_at: string;
};

export type Rejected = { title: string; score: number; reason: string };

export type LiveStep = { label: string; detail: string; state: "done" | "active" | "wait" };
