export type Clip = {
  id: string;
  title: string;
  start: string; // "3:10"
  end: string;
  score: number; // 0-100 probabilidad viral
  sizeMb: number;
  captions: string;
  thumb: string; // css gradient de demo; luego URL de Supabase Storage
  narrated?: boolean;
};

export type Rejected = { title: string; score: number; reason: string };

export type LiveStep = { label: string; detail: string; state: "done" | "active" | "wait" };
