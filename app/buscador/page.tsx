"use client";
import { useCallback, useEffect, useState } from "react";

type Search = {
  id: string;
  query: string | null;
  networks: string[];
  accounts: string[];
  links: string[];
  min_views: number;
  max_age_hours: number;
  max_results: number;
  auto_queue: number;
  content_type: string;
  publish_fb: boolean;
  status: string;
  found: number;
  queued: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

type Result = {
  id: string;
  search_id: string;
  network: string;
  url: string;
  title: string;
  views: number;
  likes: number;
  comments: number;
  duration: number;
  posted_at: string | null;
  score: number;
  velocity: number;
  status: string;
  reason: string | null;
};

const TYPES: [string, string][] = [
  ["auto", "General"], ["reality", "Reality"], ["podcast", "Podcast"], ["entrevista", "Entrevista"], ["juego", "Juegos"], ["directo", "Directo"],
];
const STATUS: Record<string, string> = { queued: "⏳ En cola", running: "🔎 Buscando", done: "✅ Listo", error: "⚠ Error" };
const RSTATUS: Record<string, string> = { found: "⚡ Encontrado", queued: "📥 Encolado", skipped: "⏭ Omitido", rejected: "🚫 Con marca" };

function ago(iso: string | null) {
  if (!iso) return "—";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 90 ? "ahora" : s < 3600 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`;
}

export default function Buscador() {
  const [searches, setSearches] = useState<Search[]>([]);
  const [results, setResults] = useState<Result[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [nets, setNets] = useState<string[]>(["tiktok", "instagram"]);
  const [fb, setFb] = useState(true);

  const load = useCallback(async () => {
    const r = await fetch("/api/buscar", { cache: "no-store" }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) return setErr(j?.error ?? "No se pudo conectar con el buscador");
    setErr("");
    setSearches(j.searches ?? []);
    setResults(j.results ?? []);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  async function buscar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    const r = await fetch("/api/buscar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: f.get("query"),
        accounts: f.get("accounts"),
        links: f.get("links"),
        networks: nets,
        min_views: f.get("min_views"),
        max_age_hours: f.get("max_age_hours"),
        max_results: f.get("max_results"),
        auto_queue: f.get("auto_queue"),
        content_type: f.get("content_type"),
        publish_fb: fb,
      }),
    }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy(false);
    if (!r?.ok) return setErr(j?.error ?? "No se pudo lanzar la búsqueda");
    setErr("");
    (e.currentTarget as HTMLFormElement).reset();
    await load();
  }

  async function encolar(searchId: string, ids: string[]) {
    if (!ids.length) return;
    setBusy(true);
    const r = await fetch("/api/buscar", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: searchId, ids }),
    }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy(false);
    if (!r?.ok) setErr(j?.error ?? "No se pudo encolar");
    await load();
  }

  const pending = searches.some((s) => s.status === "queued" || s.status === "running");

  return (
    <>
      <h1>🔎 Buscador de clips virales</h1>
      <p className="sub">
        Encuentra videos que están subiendo en TikTok e Instagram Reels, descarta los que tienen marca ajena y
        encola los mejores para convertirlos en clips. Terminan en tu web y, con la cola encendida, en Facebook.
      </p>
      {err && <div className="banner">{err}</div>}
      {pending && <div className="banner">Buscando… esta página se actualiza sola.</div>}

      <form onSubmit={buscar} className="card" style={{ display: "grid", gap: 10 }}>
        <b>Nueva búsqueda</b>
        <input name="query" placeholder="Tema o label (solo para nombrar la búsqueda): reality, podcast, comedia…" maxLength={120} />
        <textarea
          name="accounts"
          rows={2}
          placeholder="Perfiles públicos: @khaby.lame, https://www.tiktok.com/@otro, @cuenta_de_instagram"
        />
        <textarea
          name="links"
          rows={2}
          placeholder="O pega links directos de videos/reels (uno por línea)"
        />
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {(["tiktok", "instagram"] as const).map((n) => (
            <label key={n} style={{ display: "flex", gap: 5, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={nets.includes(n)}
                onChange={() => setNets((v) => (v.includes(n) ? v.filter((x) => x !== n) : [...v, n]))}
              />
              {n === "tiktok" ? "TikTok" : "Instagram Reels"}
            </label>
          ))}
          <label style={{ display: "flex", gap: 5, alignItems: "center" }}>
            <input type="checkbox" checked={fb} onChange={() => setFb((v) => !v)} />
            Publicar también en Facebook
          </label>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px,1fr))", gap: 8 }}>
          <input name="min_views" type="number" min={0} defaultValue={10000} title="Vistas mínimas" />
          <input name="max_age_hours" type="number" min={1} defaultValue={72} title="Antigüedad máxima en horas" />
          <input name="max_results" type="number" min={1} max={50} defaultValue={10} title="Resultados a guardar" />
          <input name="auto_queue" type="number" min={0} max={30} defaultValue={5} title="Clips que se encolan solos" />
          <select name="content_type">{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </div>
        <small style={{ color: "var(--muted)" }}>
          Vistas mínimas · horas de antigüedad · resultados · cuántos se encolan solos. Sin perfiles ni links, una búsqueda sin texto no encontrará nada: TikTok bloquea la búsqueda web, por eso se rastrean perfiles públicos y links.
        </small>
        <button className="btn" disabled={busy}>{busy ? "Lanzando…" : "🔎 Buscar ahora"}</button>
      </form>

      <h3 style={{ marginTop: 20 }}>Búsquedas ({searches.length})</h3>
      <div style={{ display: "grid", gap: 8 }}>
        {searches.map((s) => {
          const rows = results.filter((r) => r.search_id === s.id);
          const canQueue = rows.filter((r) => r.status === "found");
          return (
            <div key={s.id} className="card" style={{ display: "grid", gap: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <div style={{ minWidth: 240 }}>
                  <b>{s.query || "Búsqueda sin título"}</b>{" "}
                  <small style={{ color: "var(--muted)" }}>{STATUS[s.status] ?? s.status} · {ago(s.created_at)}</small>
                  <div><small style={{ color: "var(--muted)" }}>
                    {(s.accounts ?? []).join(", ") || (s.links ?? []).join(", ") || "—"}
                    {s.publish_fb ? " · web + Facebook" : " · solo web"}
                  </small></div>
                  {s.error && <div style={{ color: "var(--red, #f88)", fontSize: 12 }}>{s.error}</div>}
                </div>
                <button className="btn sm ghost" disabled={busy || !canQueue.length} onClick={() => encolar(s.id, canQueue.map((r) => r.id))}>
                  ⚡ Encolar todos ({canQueue.length})
                </button>
              </div>
              <div style={{ display: "grid", gap: 4 }}>
                {rows.map((r) => (
                  <div key={r.id} style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", fontSize: 13 }}>
                    <span>
                      <a href={r.url} target="_blank" rel="noreferrer">{r.title || r.url}</a>{" "}
                      <small style={{ color: "var(--muted)" }}>
                        {r.network} · {r.views.toLocaleString()} vistas · {r.likes.toLocaleString()} likes · {r.score} pts
                        {r.reason ? ` · ${r.reason}` : ""}
                      </small>
                    </span>
                    {r.status === "found" && (
                      <button className="btn sm ghost" disabled={busy} onClick={() => encolar(s.id, [r.id])}>📥 Encolar</button>
                    )}
                    {r.status !== "found" && <small style={{ color: "var(--muted)" }}>{RSTATUS[r.status] ?? r.status}</small>}
                  </div>
                ))}
                {!rows.length && <small style={{ color: "var(--muted)" }}>Sin resultados todavía.</small>}
              </div>
            </div>
          );
        })}
        {!searches.length && <small style={{ color: "var(--muted)" }}>Aún no hay búsquedas.</small>}
      </div>
    </>
  );
}
