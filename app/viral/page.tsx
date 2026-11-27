"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { THUMB_STYLES, breakdown, checklist, cleanTags, mmss, risksIn, titleScore } from "@/lib/viral";
import type { Viral } from "@/lib/types";

type Post = { network: string; status: string; at: string | null };
type C = {
  id: string; title: string; seconds: number; score: number; sizeMb: number; status: string | null; viral: Viral | null; hashtags: string[]; description: string;
  videoUrl?: string; thumbA?: string; thumbB?: string; thumbChoice: "a" | "b"; busy: boolean; reqAction: string | null; reqError: string | null;
  posts: Post[]; publishStatus: string | null; scheduledAt: string | null; createdAt: string;
};
type Data = { clips: C[]; counts: Record<string, number>; config: { require_approval: boolean }; migrated: boolean; demo?: boolean };

const TABS: [string, string][] = [["review", "👀 Por revisar"], ["ready", "✅ Listos"], ["approved", "✔ Aprobados"], ["rejected", "⛔ Descartados"]];
const STATUS: Record<string, string> = { review: "👀 Revísalo", pending: "⏳ Analizando", ready: "✅ Listo", approved: "✔ Aprobado", rejected: "⛔ Descartado" };
const NET: Record<string, string> = { facebook: "Facebook", instagram: "Instagram", youtube: "YouTube" };
const tone = (n: number) => (n >= 70 ? "#12c46b" : n >= 55 ? "#ffb020" : "#ff2d4f");

async function call(url: string, method: string, body: unknown): Promise<{ ok: boolean; j: any }> {
  const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => null);
  const j = await r?.json().catch(() => ({}));
  return { ok: !!r?.ok, j: j ?? {} };
}

export default function HacerloViral() {
  const [tab, setTab] = useState("review");
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [bulk, setBulk] = useState(false);

  const load = useCallback(async () => {
    const r = await fetch(`/api/viral?tab=${tab}`, { cache: "no-store" }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) return setErr(j?.error ?? "No se pudo conectar");
    setErr(""); setD(j);
  }, [tab]);
  useEffect(() => { setD(null); load(); }, [load]);
  const busyAny = !!d?.clips.some((c) => c.busy);
  useEffect(() => { const t = setInterval(load, busyAny ? 3000 : 20000); return () => clearInterval(t); }, [load, busyAny]);
  useEffect(() => { if (d && open === null && d.clips[0]) setOpen(d.clips[0].id); }, [d, open]);

  async function toggleApproval(v: boolean) {
    const { ok, j } = await call("/api/viral", "POST", { action: "config", require_approval: v });
    setNote(ok ? { ok: true, text: v ? "Listo: nada entra a la cola sin tu aprobación." : "Listo: los clips «listos» entran a la cola solos." } : { ok: false, text: j.error ?? "No se pudo guardar" });
    if (ok) load();
  }
  async function approveReady() {
    setBulk(true);
    const { ok, j } = await call("/api/viral", "POST", { action: "approve_ready" });
    setBulk(false);
    setNote(ok ? { ok: true, text: j.approved ? `${j.approved} clip(s) aprobados. Los que traen riesgo se quedan para que los decidas tú.` : "No había clips listos sin riesgo para aprobar." } : { ok: false, text: j.error ?? "No se pudo" });
    if (ok) load();
  }

  return (
    <>
      <h1>🚀 Hacerlo viral</h1>
      <p className="sub">Aquí pasa cada clip antes de salir: le pones la miniatura, escoges el mejor título y los hashtags, ves por qué tiene su puntaje y lo apruebas. El worker hace las miniaturas y los análisis nuevos en segundo plano.</p>
      {err && <div className="banner">{err}</div>}
      {note && <div className={`banner ${note.ok ? "ok" : ""}`} onClick={() => setNote(null)}>{note.text}</div>}
      {d && !d.migrated && <div className="banner">Falta correr <b>0014_viral_estudio.sql</b> en Supabase para rehacer miniaturas, elegir la A o la B y exigir aprobación.</div>}

      {d && (
        <div className="card" style={{ marginBottom: 16, display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ display: "flex", gap: 10, alignItems: "center", cursor: "pointer", flex: 1, minWidth: 260 }}>
            <input type="checkbox" checked={d.config.require_approval} onChange={(e) => toggleApproval(e.target.checked)} style={{ width: 18, height: 18 }} />
            <span><b>Aprobar yo cada clip antes de que salga</b><br /><small style={{ color: "var(--muted)" }}>Encendido: a la Cola solo entran los clips que aprobaste aquí. Apagado: entran solos los que salen «listos» (70 puntos o más).</small></span>
          </label>
          {tab === "ready" && d.clips.length > 0 && <button className="btn sm" disabled={bulk} onClick={approveReady}>{bulk ? "Aprobando…" : "✅ Aprobar todos los listos (sin riesgo)"}</button>}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {TABS.map(([k, label]) => (
          <button key={k} className={`btn sm ${tab === k ? "" : "ghost"}`} onClick={() => { setTab(k); setOpen(null); }}>
            {label}{d ? ` · ${d.counts[k] ?? 0}` : ""}
          </button>
        ))}
      </div>

      {!d && !err && <div className="card">Cargando…</div>}
      {d && d.clips.length === 0 && !err && (
        <div className="card">
          {tab === "review" ? "No tienes clips por revisar. Cuando el worker haga clips nuevos, los que necesiten tu ojo aparecen aquí." : "No hay clips en esta pestaña todavía."}
          {d.counts.ready > 0 && tab === "review" && <div style={{ marginTop: 8 }}><button className="btn sm ghost" onClick={() => setTab("ready")}>Ver los {d.counts.ready} listos</button></div>}
        </div>
      )}
      {d?.clips.map((c) => <Panel key={c.id} c={c} open={open === c.id} onToggle={() => setOpen(open === c.id ? null : c.id)} reload={load} say={setNote} />)}
    </>
  );
}

function Panel({ c, open, onToggle, reload, say }: { c: C; open: boolean; onToggle: () => void; reload: () => void; say: (n: { ok: boolean; text: string } | null) => void }) {
  const v = c.viral;
  const info = v?.thumb ?? {};
  const [title, setTitle] = useState(c.title);
  const [tags, setTags] = useState((c.hashtags ?? []).join(" "));
  const [desc, setDesc] = useState(c.description ?? "");
  const [txA, setTxA] = useState(info.a?.text ?? v?.thumb_text ?? "");
  const [txB, setTxB] = useState(info.b?.text ?? v?.thumb_texts?.[1] ?? "");
  const [stA, setStA] = useState(info.a?.style ?? "amarillo");
  const [stB, setStB] = useState(info.b?.style ?? "amarillo");
  const [tmA, setTmA] = useState<number | null>(null);
  const [tmB, setTmB] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const vid = useRef<HTMLVideoElement>(null);

  const tagList = cleanTags(tags, 8);
  const risks = Array.from(new Set([...(v?.risks ?? []), ...risksIn(title)]));
  const bd = breakdown(c.score, v ?? undefined, c.seconds, title);
  const checks = checklist({ title, hashtags: tagList, seconds: c.seconds, hasThumb: !!c.thumbA, risks, total: bd.total });
  const dirty = title !== c.title || tagList.join(" ") !== (c.hashtags ?? []).join(" ") || desc !== (c.description ?? "");
  const working = c.busy || busy;
  const ts = titleScore(title);

  async function act(body: Record<string, unknown>, okText: string) {
    setBusy(true);
    const { ok, j } = await call("/api/viral", "POST", { id: c.id, ...body });
    setBusy(false);
    say(ok ? { ok: true, text: okText } : { ok: false, text: j.error ?? "No se pudo" });
    if (ok) reload();
    return ok;
  }
  const grab = (set: (n: number) => void) => { const t = vid.current?.currentTime; if (typeof t === "number") set(Math.round(t * 100) / 100); };
  const slot = (tx: string, st: string, tm: number | null) => ({ text: tx, style: st, time: tm });

  async function schedule() {
    setBusy(true);
    const { ok, j } = await call(`/api/clips/${c.id}`, "PATCH", { auto_slot: true });
    setBusy(false);
    say(ok ? { ok: true, text: "Programado en Facebook a la mejor hora libre. Míralo en Cola." } : { ok: false, text: j.error ?? "No se pudo programar" });
    if (ok) reload();
  }

  const pickLabel = (k: "a" | "b") => (c.thumbChoice === k ? "✔ Se publica esta" : "Usar esta al publicar");
  const thumbCard = (k: "a" | "b") => {
    const img = k === "a" ? c.thumbA : c.thumbB;
    const tx = k === "a" ? txA : txB, setTx = k === "a" ? setTxA : setTxB;
    const st = k === "a" ? stA : stB, setSt = k === "a" ? setStA : setStB;
    const tm = k === "a" ? tmA : tmB, setTm = k === "a" ? setTmA : setTmB;
    const saved = k === "a" ? info.a : info.b;
    return (
      <div style={{ border: `2px solid ${c.thumbChoice === k && img ? "#12c46b" : "var(--line)"}`, borderRadius: 14, padding: 10, flex: 1, minWidth: 210 }}>
        <b>Miniatura {k.toUpperCase()}{k === "b" ? " (prueba)" : ""}</b>
        <div style={{ margin: "8px 0", aspectRatio: "9 / 16", maxHeight: 300, background: "#0b0d22", borderRadius: 10, overflow: "hidden", display: "grid", placeItems: "center" }}>
          {img ? <img src={img} alt={`Miniatura ${k}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <small style={{ color: "var(--muted)", padding: 10, textAlign: "center" }}>{k === "b" ? "Aún no hay miniatura B. Escribe un texto y créala." : "Sin miniatura todavía."}</small>}
        </div>
        {img && <button className={`btn sm ${c.thumbChoice === k ? "" : "ghost"}`} style={{ width: "100%", marginBottom: 8 }} disabled={working || c.thumbChoice === k} onClick={() => act({ action: "choose_thumb", choice: k }, `Se publicará la miniatura ${k.toUpperCase()}.`)}>{pickLabel(k)}</button>}
        <input value={tx} maxLength={40} onChange={(e) => setTx(e.target.value)} placeholder="Texto corto (2 a 4 palabras)" style={{ width: "100%", marginBottom: 6 }} />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
          {THUMB_STYLES.map((s) => (
            <button key={s.id} className={`btn sm ${st === s.id ? "" : "ghost"}`} style={{ padding: "4px 9px" }} onClick={() => setSt(s.id)}><span style={{ color: s.color, textShadow: "0 0 2px #000" }}>●</span> {s.label}</button>
          ))}
        </div>
        <small style={{ color: "var(--muted)", display: "block", marginBottom: 6 }}>
          Cuadro: {tm !== null ? `${mmss(tm)} (nuevo)` : saved?.time != null ? `${mmss(saved.time)} (el de ahora)` : "el mejor, lo elige solo"}
        </small>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button className="btn sm ghost" disabled={!c.videoUrl} onClick={() => grab(setTm)} title="Pausa el video donde quieras y toca aquí">📍 Usar el cuadro del video</button>
          <button className="btn sm" disabled={working || !c.videoUrl} onClick={() => act({ action: "thumbs", [k]: slot(tx, st, tm) }, `Pedí la miniatura ${k.toUpperCase()}. El worker la hace en segundos.`)}>{img ? "🔄 Rehacer" : "✨ Crear"}</button>
        </div>
      </div>
    );
  };

  return (
    <div className="card" style={{ marginBottom: 14, borderColor: open ? "rgba(124,77,255,.55)" : undefined }}>
      <div onClick={onToggle} style={{ display: "flex", gap: 12, alignItems: "center", cursor: "pointer" }}>
        <div style={{ width: 46, aspectRatio: "9 / 16", borderRadius: 8, overflow: "hidden", background: "#0b0d22", flex: "none" }}>
          {(c.thumbChoice === "b" && c.thumbB ? c.thumbB : c.thumbA) && <img src={(c.thumbChoice === "b" && c.thumbB ? c.thumbB : c.thumbA)!} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <b style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.title}</b>
          <small style={{ color: "var(--muted)" }}>{STATUS[c.status ?? ""] ?? "—"} · {c.seconds} s{risks.length ? " · ⚠️ riesgo" : ""}{!c.thumbA ? " · sin miniatura" : ""}{c.posts.length ? ` · en cola: ${c.posts.map((p) => NET[p.network] ?? p.network).join(", ")}` : ""}</small>
        </div>
        {working && <small style={{ color: "#ffb020" }}>⏳ trabajando…</small>}
        <div style={{ fontWeight: 800, fontSize: 20, color: tone(v?.score ?? c.score) }}>{v?.score ?? "—"}</div>
        <span style={{ color: "var(--muted)" }}>{open ? "▴" : "▾"}</span>
      </div>

      {open && (
        <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "minmax(200px, 260px) 1fr", gap: 18, alignItems: "start" }}>
          <div>
            {c.videoUrl ? <video ref={vid} src={c.videoUrl} controls playsInline preload="metadata" style={{ width: "100%", aspectRatio: "9 / 16", background: "#000", borderRadius: 12, objectFit: "cover" }} /> : <div className="banner">Este clip no tiene video.</div>}
            <small style={{ color: "var(--muted)" }}>{c.seconds} s · {c.sizeMb} MB. Pausa el video en el cuadro que más te guste y usa «📍 Usar el cuadro del video» en la miniatura.</small>
          </div>

          <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
            {risks.length > 0 && <div className="banner" style={{ margin: 0 }}>⚠️ Riesgo para Facebook: {risks.join(", ")}. Revísalo antes de aprobar.</div>}
            {c.reqError && <div className="banner" style={{ margin: 0 }}>No se pudo: {c.reqError}</div>}
            {c.busy && <div className="banner ok" style={{ margin: 0 }}>⏳ El worker está {c.reqAction === "reanalyze" ? "analizando de nuevo" : "haciendo la miniatura"}. Se actualiza solo.</div>}

            <section>
              <h3 style={{ margin: "0 0 8px" }}>1 · Miniatura</h3>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>{thumbCard("a")}{thumbCard("b")}</div>
              <small style={{ color: "var(--muted)", display: "block", marginTop: 6 }}>Instagram y YouTube usan la que marques con «Se publica esta». Facebook Reels no deja subir miniatura propia por la API; ahí sale la que Facebook escoja.</small>
            </section>

            <section>
              <h3 style={{ margin: "0 0 8px" }}>2 · Título <span style={{ fontSize: 13, color: tone(ts) }}>({ts}/100)</span></h3>
              <input value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} style={{ width: "100%" }} />
              <small style={{ color: "var(--muted)" }}>{title.trim().length} caracteres · lo ideal: 25 a 65, con curiosidad y sin contar el final.</small>
              {(v?.titles ?? []).length > 0 && (
                <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                  {(v?.titles ?? []).map((t) => (
                    <div key={t.t} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontWeight: 700, color: tone(t.score), width: 30 }}>{t.score}</span>
                      <span style={{ flex: 1 }}>{t.t}{t.angle ? <small style={{ color: "var(--muted)" }}> · {t.angle}</small> : null}</span>
                      <button className="btn sm ghost" disabled={t.t === title} onClick={() => setTitle(t.t)}>Usar</button>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ marginTop: 8 }}><button className="btn sm ghost" disabled={working} onClick={() => act({ action: "reanalyze" }, "Pedí un análisis nuevo a la IA. Los títulos y hashtags nuevos salen en unos segundos.")}>🔄 Pedir otros títulos a la IA</button></div>
            </section>

            <section>
              <h3 style={{ margin: "0 0 8px" }}>3 · Hashtags y descripción</h3>
              <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="#fyp #tema ..." style={{ width: "100%" }} />
              <small style={{ color: "var(--muted)" }}>{tagList.length ? tagList.join(" ") : "Sin hashtags"} · ideal: 1 amplio (#fyp), 1 o 2 del programa y el resto del tema.</small>
              {(v?.hashtags ?? []).length > 0 && tagList.join(" ") !== (v?.hashtags ?? []).join(" ") && (
                <div><small>Sugeridos por la IA: {(v?.hashtags ?? []).join(" ")} <a href="#" onClick={(e) => { e.preventDefault(); setTags((v?.hashtags ?? []).join(" ")); }}>usar estos</a></small></div>
              )}
              <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} maxLength={2200} placeholder="Descripción para publicar (opcional)" style={{ width: "100%", marginTop: 8 }} />
              <div style={{ marginTop: 8 }}><button className="btn sm" disabled={working || !dirty} onClick={() => act({ action: "edit", title, hashtags: tagList, description: desc }, "Guardado. La cola y los textos por red ya usan esto.")}>💾 Guardar título, hashtags y descripción</button>{dirty && <small style={{ color: "#ffb020" }}> · tienes cambios sin guardar</small>}</div>
            </section>

            <section>
              <h3 style={{ margin: "0 0 8px" }}>4 · Por qué tiene este puntaje</h3>
              <div style={{ display: "grid", gap: 6 }}>
                {bd.parts.map((p) => (
                  <div key={p.key} style={{ display: "grid", gridTemplateColumns: "210px 1fr 70px", gap: 8, alignItems: "center", fontSize: 13 }}>
                    <span>{p.label} <small style={{ color: "var(--muted)" }}>({p.pct}%)</small></span>
                    <div style={{ background: "#0b0d22", borderRadius: 6, height: 8 }}><div style={{ width: `${Math.max(2, p.value)}%`, height: 8, borderRadius: 6, background: tone(p.value) }} /></div>
                    <span style={{ textAlign: "right" }}>{Math.round(p.value)} → +{p.points}</span>
                  </div>
                ))}
                <div style={{ textAlign: "right", fontWeight: 700, color: tone(bd.total) }}>Total con tu título: {bd.total}/100</div>
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: "10px 0 0", display: "grid", gap: 4, fontSize: 14 }}>
                {checks.map((k) => <li key={k.text}>{k.ok ? "✅" : k.warn ? "🟡" : "❌"} {k.text}</li>)}
              </ul>
              <small style={{ color: "var(--muted)" }}>El puntaje es una guía (IA + reglas), no una garantía de que se haga viral.</small>
            </section>

            <section style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", borderTop: "1px solid var(--line)", paddingTop: 14 }}>
              {c.status !== "approved" && <button className="btn" disabled={working} onClick={() => act({ action: "approve" }, "Aprobado. Entra a la Cola si está encendida.")}>✅ Aprobar y mandar a la cola</button>}
              {c.publishStatus !== "published" && <button className="btn sm ghost" disabled={working} onClick={schedule}>🕐 Programar en Facebook a la mejor hora</button>}
              {c.status !== "rejected" && <button className="btn sm ghost" disabled={working} onClick={() => act({ action: "reject" }, "Descartado.")}>🗑 Descartar</button>}
              {(c.status === "approved" || c.status === "rejected") && <button className="btn sm ghost" disabled={working} onClick={() => act({ action: "reopen" }, "Volvió a «Por revisar».")}>↩ Volver a revisar</button>}
              {c.posts.length > 0 && <small style={{ color: "var(--muted)" }}>{c.posts.map((p) => `${NET[p.network] ?? p.network}: ${p.status === "published" ? "publicado" : p.status === "error" ? "con error" : "en cola"}`).join(" · ")}</small>}
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
