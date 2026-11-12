"use client";
import { useEffect, useState } from "react";
import { SUB_PRESETS, logoStyle, toHash, useBrand, type Brand, type Subs } from "@/lib/useBrand";

const POSITIONS: [string, string][] = [["bc", "Abajo al centro"], ["bl", "Abajo a la izquierda"], ["br", "Abajo a la derecha"], ["tc", "Arriba al centro"], ["tl", "Arriba a la izquierda"], ["tr", "Arriba a la derecha"]];

function LogoSection() {
  const { brand, logoUrl, reload } = useBrand();
  const [form, setForm] = useState<Brand>({ enabled: true, pos: "bc", size: 24, opacity: 100 });
  const [file, setFile] = useState<File | null>(null);
  const [local, setLocal] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (brand) setForm(brand); }, [brand]);
  useEffect(() => {
    if (!file) return setLocal(null);
    const u = URL.createObjectURL(file);
    setLocal(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  async function save() {
    setBusy(true); setMsg(null);
    const f = new FormData();
    f.set("enabled", String(form.enabled)); f.set("pos", form.pos); f.set("size", String(form.size)); f.set("opacity", String(form.opacity));
    if (file) f.set("file", file);
    const r = await fetch("/api/brand", { method: "POST", body: f }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setMsg(r?.ok ? { ok: true, text: "Guardado. El worker lo usa en los próximos clips." } : { ok: false, text: j?.error ?? "No se pudo guardar" });
    if (r?.ok) { setFile(null); reload(); }
    setBusy(false);
  }
  async function remove() {
    if (!confirm("¿Quitar tu logo?")) return;
    await fetch("/api/brand", { method: "DELETE" });
    setFile(null); reload(); setMsg({ ok: true, text: "Logo quitado." });
  }

  const shown = local ?? logoUrl;
  const set = (p: Partial<Brand>) => setForm((x) => ({ ...x, ...p }));
  return (
    <div className="card neon" style={{ maxWidth: 720, marginBottom: 18 }}>
      <h3 style={{ marginBottom: 6 }}>🏷️ Tu logo / marca</h3>
      <p className="sub" style={{ marginBottom: 14, fontSize: 13 }}>Se pega en todos los clips (vertical, dividido, dos personas y difuminado). Lo mejor es un PNG con fondo transparente.</p>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 280px", minWidth: 0 }}>
          <label>Imagen del logo (PNG, JPG o WEBP · máx. 3 MB)</label>
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <label style={{ marginTop: 12 }}>Posición</label>
          <select value={form.pos} onChange={(e) => set({ pos: e.target.value })}>{POSITIONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
          <label style={{ marginTop: 12 }}>Tamaño: {form.size}% del ancho</label>
          <input type="range" min={5} max={60} value={form.size} onChange={(e) => set({ size: Number(e.target.value) })} />
          <label style={{ marginTop: 12 }}>Opacidad: {form.opacity}%</label>
          <input type="range" min={10} max={100} value={form.opacity} onChange={(e) => set({ opacity: Number(e.target.value) })} />
          <label style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center", textTransform: "none", fontSize: 14, color: "var(--text)" }}>
            <input type="checkbox" checked={form.enabled} onChange={(e) => set({ enabled: e.target.checked })} style={{ width: "auto" }} /> Poner el logo en los clips
          </label>
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button className="btn sm" onClick={save} disabled={busy || (!file && !logoUrl)}>{busy ? "Guardando…" : "Guardar"}</button>
            {logoUrl && <button className="btn sm ghost" onClick={remove}>Quitar logo</button>}
          </div>
          {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 12, marginBottom: 0 }}>{msg.text}</div>}
        </div>
        <div style={{ flex: "0 0 150px" }}>
          <div style={{ position: "relative", width: 150, aspectRatio: "9 / 16", background: "linear-gradient(180deg,#2a2f5a,#12142b)", borderRadius: 14, overflow: "hidden", border: "1px solid var(--line)" }}>
            {shown && form.enabled && <img src={shown} alt="" style={logoStyle(form)} />}
          </div>
          <small style={{ color: "var(--muted)", display: "block", textAlign: "center", marginTop: 6 }}>Así quedará</small>
        </div>
      </div>
    </div>
  );
}

function SubsSection() {
  const { brand, reload } = useBrand();
  const [subs, setSubs] = useState<Subs>(SUB_PRESETS.classic.v);
  const [hook, setHook] = useState(true);
  const [hookSec, setHookSec] = useState(3.5);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!brand) return;
    if (brand.subs) setSubs(brand.subs);
    if (brand.hook !== undefined) setHook(brand.hook);
    if (brand.hook_sec) setHookSec(brand.hook_sec);
  }, [brand]);

  const set = (p: Partial<Subs>) => setSubs((x) => ({ ...x, ...p }));
  async function save() {
    setBusy(true); setMsg(null);
    const f = new FormData();
    f.set("subs", JSON.stringify(subs)); f.set("hook", String(hook)); f.set("hook_sec", String(hookSec));
    const r = await fetch("/api/brand", { method: "POST", body: f }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setMsg(r?.ok ? { ok: true, text: "Guardado. Se usa en los próximos clips." } : { ok: false, text: j?.error ?? "No se pudo guardar" });
    if (r?.ok) reload();
    setBusy(false);
  }

  const sample = ["ESTO", "ES", "UN", "CLIP"].map((w, i) => (
    <span key={w} style={{ color: i === 1 ? toHash(subs.active) : toHash(subs.text), marginRight: 10, WebkitTextStroke: `${Math.max(1, subs.outline_w / 3)}px ${toHash(subs.outline)}`, paintOrder: "stroke fill" }}>{subs.upper ? w : w.toLowerCase()}</span>
  ));
  return (
    <div className="card neon" style={{ maxWidth: 720, marginBottom: 18 }}>
      <h3 style={{ marginBottom: 6 }}>💬 Subtítulos y texto gancho</h3>
      <p className="sub" style={{ marginBottom: 14, fontSize: 13 }}>Elige cómo se ven los subtítulos de tus clips. El texto gancho es una frase corta que la IA pone arriba al empezar el clip.</p>
      <label>Estilo listo</label>
      <select value="" onChange={(e) => e.target.value && setSubs(SUB_PRESETS[e.target.value].v)}>
        <option value="">Elegir un estilo…</option>
        {Object.entries(SUB_PRESETS).map(([k, p]) => <option key={k} value={k}>{p.label}</option>)}
      </select>
      <div style={{ background: "#1b1e3a", borderRadius: 12, padding: "22px 12px", textAlign: "center", fontWeight: 800, fontSize: Math.max(18, subs.size / 3), margin: "14px 0" }}>{sample}</div>
      <div className="row" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
        <div><label>Color del texto</label><input type="color" value={toHash(subs.text)} onChange={(e) => set({ text: e.target.value })} style={{ height: 42, padding: 3 }} /></div>
        <div><label>Palabra activa</label><input type="color" value={toHash(subs.active)} onChange={(e) => set({ active: e.target.value })} style={{ height: 42, padding: 3 }} /></div>
        <div><label>Borde</label><input type="color" value={toHash(subs.outline)} onChange={(e) => set({ outline: e.target.value })} style={{ height: 42, padding: 3 }} /></div>
      </div>
      <label style={{ marginTop: 12 }}>Tamaño: {subs.size}</label>
      <input type="range" min={50} max={130} value={subs.size} onChange={(e) => set({ size: Number(e.target.value) })} />
      <label style={{ marginTop: 12 }}>Grosor del borde: {subs.outline_w}</label>
      <input type="range" min={0} max={14} value={subs.outline_w} onChange={(e) => set({ outline_w: Number(e.target.value) })} />
      <label style={{ marginTop: 12 }}>Altura: {subs.offset === 0 ? "la de siempre" : subs.offset > 0 ? `${subs.offset} px más arriba` : `${-subs.offset} px más abajo`}</label>
      <input type="range" min={-300} max={400} step={10} value={subs.offset} onChange={(e) => set({ offset: Number(e.target.value) })} />
      <div style={{ display: "flex", gap: 22, flexWrap: "wrap", marginTop: 12 }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center", textTransform: "none", fontSize: 14, color: "var(--text)" }}><input type="checkbox" checked={subs.upper} onChange={(e) => set({ upper: e.target.checked })} style={{ width: "auto" }} /> MAYÚSCULAS</label>
        <label style={{ display: "flex", gap: 8, alignItems: "center", textTransform: "none", fontSize: 14, color: "var(--text)" }}><input type="checkbox" checked={subs.pop} onChange={(e) => set({ pop: e.target.checked })} style={{ width: "auto" }} /> Efecto “pop” en cada palabra</label>
      </div>
      <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "16px 0" }} />
      <label style={{ display: "flex", gap: 8, alignItems: "center", textTransform: "none", fontSize: 14, color: "var(--text)" }}><input type="checkbox" checked={hook} onChange={(e) => setHook(e.target.checked)} style={{ width: "auto" }} /> Poner texto gancho arriba al empezar el clip</label>
      {hook && <><label style={{ marginTop: 10 }}>Se ve durante {hookSec.toFixed(1)} s</label><input type="range" min={1.5} max={6} step={0.5} value={hookSec} onChange={(e) => setHookSec(Number(e.target.value))} /></>}
      <div style={{ marginTop: 14 }}><button className="btn sm" onClick={save} disabled={busy}>{busy ? "Guardando…" : "Guardar estilo"}</button></div>
      {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 12, marginBottom: 0 }}>{msg.text}</div>}
    </div>
  );
}

export default function Ajustes() {
  const rows: [string, string, string][] = [
    ["Quién elige los clips", "LLM_PROVIDER", "groq (gratis) o anthropic"],
    ["Modelo de Groq", "GROQ_MODEL", "llama-3.3-70b-versatile"],
    ["Idioma del video", "LANGUAGE", "es"],
    ["Formato vertical", "CLIP_LAYOUT", "crop, split (cara arriba + gameplay), duo (dos personas) o blur"],
    ["Seguir a quien habla", "CLIP_FRAMING", "auto (sigue la cara) o center (fijo)"],
    ["Calidad del video", "CLIP_CRF", "18 (más bajo = más nítido y pesado)"],
    ["Encuadre del recorte", "CLIP_FOCUS_X", "0 = izquierda, 0.5 = centro, 1 = derecha"],
    ["Segundos por trozo (En vivo)", "SEGMENT_SECONDS", "120"],
    ["Puntaje mínimo En vivo", "LIVE_MIN_SCORE", "55"],
    ["Transcripción local", "WHISPER_MODEL", "small (solo si no usas Groq)"],
  ];
  return (
    <>
      <h1>Ajustes de IA</h1>
      <LogoSection />
      <SubsSection />
      <p className="sub">Por ahora estos ajustes se cambian en el archivo <code>worker/.env</code> y se aplican al reiniciar el worker.</p>
      <div className="card neon" style={{ maxWidth: 720 }}>
        {rows.map(([label, key, hint]) => (
          <div key={key} style={{ padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
            <b>{label}</b><br />
            <code>{key}</code> <span style={{ color: "var(--muted)", fontSize: 13 }}>· {hint}</span>
          </div>
        ))}
        <p className="sub" style={{ marginTop: 14, marginBottom: 0, fontSize: 13 }}>
          La cantidad de clips, la duración y la calidad se eligen en “Crear clips”.
        </p>
      </div>
    </>
  );
}
