"use client";
import { useEffect, useState } from "react";
import CropPreview from "@/components/CropPreview";
import PromoBanner from "@/components/PromoBanner";
import CommunityFeed from "@/components/CommunityFeed";

type Layout = "crop" | "split" | "blur";
type Src = "twitch" | "kick" | "archivo";
const LAYOUTS: [Layout, string][] = [["crop", "Vertical"], ["split", "Dividido"], ["blur", "Fondo difuminado"]];
const PH: Record<Src, string> = { twitch: "https://www.twitch.tv/videos/…", kick: "https://kick.com/…/videos/…", archivo: "https://… (YouTube o enlace directo .mp4)" };

function Phone({ layout, caption }: { layout: Layout; caption: string }) {
  const game = "linear-gradient(180deg,#7bb7ff,#4a7a3a)";
  const cam = "linear-gradient(160deg,#ff6ad5,#8b3dff)";
  return (
    <div className="phone">
      <span className="badge">DE LA COMUNIDAD</span>
      {layout === "split" && (<>
        <div className="zone" style={{ top: 0, height: "38%", background: cam }}>Cámara</div>
        <div className="zone" style={{ top: "38%", bottom: 0, background: game }}>Juego</div>
      </>)}
      {layout === "crop" && <div className="zone" style={{ inset: 0, background: game }}>Recorte vertical del juego</div>}
      {layout === "blur" && (<>
        <div className="zone" style={{ inset: 0, background: game, filter: "blur(18px) brightness(.6)" }} />
        <div className="zone" style={{ top: "30%", height: "40%", background: "linear-gradient(160deg,#4a7a3a,#2a4a6a)" }}>Video completo</div>
      </>)}
      <div className="cap2">{caption}</div>
    </div>
  );
}

export default function Crear() {
  const [src, setSrc] = useState<Src>("twitch");
  const [url, setUrl] = useState("");
  const [layout, setLayout] = useState<Layout>("crop");
  const [crop, setCrop] = useState({ x: 10, y: 10, w: 80, h: 60 });
  const [name, setName] = useState("");
  const [adv, setAdv] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [stats, setStats] = useState<{ clips: number; creators: number; users: number } | null>(null);

  useEffect(() => {
    try { setName(localStorage.getItem("cf_clipper") || ""); } catch {}
    fetch("/api/hub/stats").then((r) => r.json()).then((j) => j.stats && setStats(j.stats)).catch(() => {});
  }, []);

  const step = !url ? 1 : msg?.ok ? 4 : adv ? 2 : 3;
  const canPreview = /youtu\.?be|\.mp4|\.webm/i.test(url);

  async function paste() {
    try { setUrl(await navigator.clipboard.readText()); } catch { setMsg({ ok: false, text: "No pude leer el portapapeles: pega con Ctrl+V." }); }
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!url.trim()) return setMsg({ ok: false, text: "Pega el link del stream primero." });
    setBusy(true); setMsg(null);
    const f = new FormData(e.currentTarget);
    const clipper = name.trim();
    try { if (clipper) localStorage.setItem("cf_clipper", clipper); } catch {}
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "vod_url", url: url.trim(), range_from: f.get("from"), range_to: f.get("to"),
        clip_seconds: Number(f.get("secs")), clips: Number(f.get("count")), quality: f.get("quality"),
        layout, custom_crop: layout === "crop" && adv ? crop : null, clipper,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && !data.demo) { window.location.href = "/biblioteca"; return; }
    setMsg(res.ok ? { ok: true, text: data.message } : { ok: false, text: data.error ?? "Error" });
    setBusy(false);
  }

  const tab = (k: Src, label: string) => (
    <button type="button" className={`tab ${k === "kick" ? "kick" : ""} ${src === k ? "on" : ""}`} onClick={() => setSrc(k)}>{label}</button>
  );

  return (
    <>
      <div className="cols" style={{ gridTemplateColumns: "1fr 1.1fr 1fr", marginTop: 0 }}>
        <PromoBanner variant="ad" />
        <div className="hero">
          <h1>Convertí tus streams en <em>clips virales</em></h1>
          <small style={{ color: "var(--muted)" }}>Vertical, con subtítulos y listo para TikTok, Reels y Shorts. En minutos.</small>
        </div>
        <PromoBanner variant="reach" />
      </div>

      <div className="cols">
        {/* IZQUIERDA: fuente */}
        <form className="card" onSubmit={submit}>
          <h3 style={{ fontSize: 13, color: "var(--muted)", letterSpacing: ".08em", marginBottom: 16 }}>SOURCE VIDEO</h3>
          <div className="tabs3">{tab("kick", "KICK")}{tab("twitch", "Twitch")}{tab("archivo", "Archivo")}</div>
          <label style={{ textAlign: "center", textTransform: "none", fontSize: 15, color: "var(--text)", fontWeight: 600 }}>
            {src === "archivo" ? "Pega el link del video" : "Pegá el link del stream"}
          </label>
          <div className="pasterow">
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={PH[src]} />
            <button type="button" className="btn ghost sm" onClick={paste}>Pegar</button>
          </div>
          <small style={{ display: "block", textAlign: "center", color: "var(--muted)", margin: "8px 0 16px" }}>Ejemplo: twitch.tv/videos/123456789 o un clip</small>

          <div className="row" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            <div><label>Desde</label><input name="from" placeholder="0:00" /></div>
            <div><label>Hasta</label><input name="to" placeholder="1:00" /></div>
            <div><label>Duración</label><select name="secs" defaultValue="45"><option value="30">30 s</option><option value="45">45 s</option><option value="60">60 s</option></select></div>
            <div><label>Cantidad</label><select name="count" defaultValue="5"><option>1</option><option>3</option><option>5</option><option>10</option></select></div>
          </div>
          <div className="row" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div><label>Calidad</label><select name="quality" defaultValue="1080p"><option value="720p">720p</option><option value="1080p">1080p</option></select></div>
            <div><label>Tu nombre (ranking)</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="ej. Juan" maxLength={40} /></div>
          </div>

          <label>Encuadre en el teléfono</label>
          <div className="tabs3">{LAYOUTS.map(([k, l]) => (
            <button type="button" key={k} className={`tab ${layout === k ? "on" : ""}`} style={{ fontSize: 12 }} onClick={() => setLayout(k)}>{l}</button>
          ))}</div>

          <button className="btn" style={{ width: "100%", marginTop: 6 }} disabled={busy}>{busy ? "Importando…" : "Importar link y generar clips"}</button>
          {msg && <div className={`banner ${msg.ok ? "ok" : ""}`} style={{ marginTop: 14, marginBottom: 0 }}>{msg.text}</div>}

          {stats && (
            <div className="stat"><div className="ic">✂</div><div><b>{stats.clips.toLocaleString("es")}</b><span>Clips creados</span></div></div>
          )}
        </form>

        {/* CENTRO: teléfono */}
        <div className="card neon" style={{ padding: 0, overflow: "hidden" }}>
          <h3 style={{ padding: "16px 20px", fontSize: 15, color: "#b79bff", borderBottom: "1px solid var(--line)" }}>📱 ASÍ SE VEN TUS CLIPS</h3>
          <div style={{ padding: 20 }}>
            <Phone layout={layout} caption="Clip sin título" />
            <small style={{ display: "block", textAlign: "center", color: "var(--muted)", margin: "14px 0 6px" }}>Clips de la comunidad · tocá los costados para pasar</small>
            {layout === "crop" && canPreview && (
              <>
                <button type="button" className="btn ghost sm" style={{ width: "100%" }} onClick={() => setAdv(!adv)}>{adv ? "Usar encuadre automático" : "Ajustar encuadre a mano"}</button>
                {adv && <div style={{ marginTop: 12 }}><CropPreview videoUrl={url} onCropChange={setCrop} /></div>}
              </>
            )}
            {stats && <div className="stat" style={{ marginTop: 16 }}><div className="ic">✨</div><div><b>{stats.creators.toLocaleString("es")}</b><span>Creadores de clips</span></div></div>}
          </div>
        </div>

        {/* DERECHA: cómo funciona */}
        <div className="card">
          <h3 style={{ fontSize: 13, color: "var(--muted)", letterSpacing: ".08em", marginBottom: 10 }}>CÓMO FUNCIONA</h3>
          <ul className="how" style={{ padding: 0 }}>
            {["Subir el video", "Elegir el encuadre", "Generar el clip", "Descargar y publicar en el Top"].map((t, i) => (
              <li key={t} className={step === i + 1 ? "on" : ""}><span className="n">{i + 1}</span>{t}</li>
            ))}
          </ul>
          <div className="why" style={{ color: "var(--text)" }}>
            <b>Paso 1:</b> pegá un link de Twitch o Kick. Después elegís cómo se ve en el teléfono: vertical, dividido (cámara arriba, juego abajo) o con fondo difuminado.
          </div>
          {stats && <div className="stat" style={{ marginTop: 18 }}><div className="ic">👥</div><div><b>{stats.users.toLocaleString("es")}</b><span>Usuarios registrados</span></div></div>}
          <h3 style={{ fontSize: 14, margin: "26px 0 10px" }}>Últimos clips de la comunidad</h3>
          <CommunityFeed kind="feed" limit={8} />
        </div>
      </div>
    </>
  );
}
