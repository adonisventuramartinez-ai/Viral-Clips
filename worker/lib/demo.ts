import type { Clip, Rejected, LiveStep } from "./types";

const g = (a: string, b: string) => `linear-gradient(160deg, ${a}, ${b})`;

export const demoClips: Clip[] = [
  { id: "1", title: "Se arregló con la dueña del pleito", start: "3:10", end: "4:07", score: 68, sizeMb: 62.9, captions: "SE ARREGLÓ CON LA DUEÑA", thumb: g("#3a0d18", "#0d1a2b") },
  { id: "2", title: "Hay una que viaja con visa", start: "2:52", end: "3:35", score: 65, sizeMb: 90.5, captions: "HAY UNA QUE VIAJA CON VISA", thumb: g("#2b0d3a", "#101a2b") },
  { id: "3", title: "No, yo estaré ahí, yo estaré", start: "1:12", end: "1:58", score: 61, sizeMb: 111.2, captions: "NO YO ESTARÉ AHÍ", thumb: g("#0d2b2b", "#1a0d2b") },
  { id: "4", title: "Como dijo el doctor", start: "5:20", end: "6:02", score: 57, sizeMb: 84.5, captions: "COMO DIJO EL DOCTOR", thumb: g("#3a1a0d", "#0d1a3a") },
];

export const demoRejected: Rejected[] = [
  { title: "Yo soy como Cristóbal Colón", score: 9, reason: "Ese momento o tema ya tiene clip" },
  { title: "Las hijas son todas hermanas", score: 7, reason: "Ya se eligieron 2 mejores en esta revisión" },
  { title: "Hacen cinco trap por corrido", score: 7, reason: "Ya se eligieron 2 mejores en esta revisión" },
  { title: "Yo estuve preso, sé lo que es", score: 8, reason: "Ese momento o tema ya tiene clip" },
];

export const demoSteps: LiveStep[] = [
  { label: "Conectando con el directo", detail: "", state: "done" },
  { label: "Grabando", detail: "30:24", state: "active" },
  { label: "Transcribiendo", detail: "30:00", state: "active" },
  { label: "Buscando momentos virales", detail: "13 revisiones · 1072 mensajes del chat", state: "active" },
  { label: "Creando clips", detail: "7 listos · 1 en cola", state: "active" },
];
