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
  pack?: Pack;
  thumbUrl?: string;
  scheduledAt?: string;
  publishStatus?: "scheduled" | "published" | "error";
  publishError?: string;
  viral?: Viral;
  viralStatus?: "pending" | "ready" | "review" | "rejected" | "approved";
  thumbBUrl?: string;
  thumbChoice?: "a" | "b";
};

export type Viral = {
  score: number;
  verdict: "ready" | "review" | "rejected";
  title: string;
  title_original?: string;
  titles?: { t: string; angle?: string; score: number }[];
  hook_score?: number;
  thumb_text?: string;
  hashtags?: string[];
  thumb_texts?: string[];
  /** Lo que elegiste en Hacerlo viral para cada miniatura: texto, estilo y segundo del cuadro. */
  thumb?: { a?: ThumbInfo; b?: ThumbInfo };
  risks?: string[];
  source?: string;
};

export type ThumbInfo = { text?: string; style?: string; time?: number | null };

export type Pack = {
  tiktok?: { caption?: string; hashtags?: string[] };
  reels?: { caption?: string; hashtags?: string[] };
  shorts?: { title?: string; description?: string; hashtags?: string[] };
  hooks?: string[];
  first_comment?: string;
  source?: string;
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
