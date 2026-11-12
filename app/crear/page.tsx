"use client";
import { useEffect, useMemo, useState } from "react";
import CropPreview from "@/components/CropPreview";
import CommunityFeed from "@/components/CommunityFeed";
import PhonePreview, { type Layout } from "@/components/PhonePreview";
import { ASPECT_CAM, ASPECT_VERT, DEFAULT_CAM, DEFAULT_CROP, parseEmbed, round2, toSeconds, type Box } from "@/lib/embed";

type Src = "twitch" | "kick" | "archivo";
const LAYOUTS: [Layout, string][] = [["crop", "Vertical"], ["split", "Dividido"], ["duo", "Dos personas"], ["blur", "Fondo difuminado"]];
const PH: Record<Src, string> = { twitch: "https://www.twitch.tv/videos/…", kick: "https://kick.com/…/videos/…", archivo: "https://… (YouTube o enlace directo .mp4)" };

export default function Crear() {
  const [src, setSrc] = useState<Src>("twitch");
  const [url, setUrl] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [layout, setLayout] = useState<Layout>("crop");
  const [cropBox, setCropBox] = useState<Box>(DEFAULT_CROP);
  const [camBox, setCamBox] = useState<Box>(DEFAULT_CAM);
  const [manualCrop, setManualCrop] = useState(false); // vertical: false = sigue a la persona (automático)
  const [manualCam, setManualCam] = useState(true); // dividido: true = tú marcas dónde está la cámara
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [stats, setStats] = useState<{ clips: number; creators: number; users: number } | null>(null);

  useEffect(() => {
    try { setName(localStorage.getItem("cf_clipper") || ""); } catch {}
    fetch("/api/hub/stats").then((r) => r.json()).then((j) => j.stats && setStats(j.stats)).catch(() => {});
  }, []);

  const startSec = toSeconds(from);
  const embed = useMemo(() => parseEmbed(url, startSec), [url, startSec]);
  const live = embed.kind !== "none";
  const isKick = /kick\.com/i.test(url);

  // Recuadro que realmente se enviará al worker (null = que lo decida la IA)
  const sentBox: Box | null = !live ? null : layout === "crop" ? (manualCrop ? cropBox : null) : layout === "split" ? (manualCam ? camBox : null) : null;
  const previewCrop = layout === "crop" && manualCrop ? cropBox : null;
  const previewCam = layout === "split" && manualCam ? camBox : null;

  const step = !url ? 1 : msg?.ok ? 4 : layout !== "crop" || manualCrop ? 2 : 3;

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
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "vod_url", url: url.trim(), range_from: from || null, range_to: to || null,
          clip_seconds: Number(f.get("secs")), clips: Number(f.get("count")), quality: f.get("quality"),
          layout, custom_crop: sentBox ? round2(sentBox) : null, clipper,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && !data.demo) { window.location.href = "/biblioteca"; return; }
      setMsg(res.ok ? { ok: true, text: data.message } : { ok: false, text: data.error ?? "Error" });
    } catch {
      setMsg({ ok: false, text: "No se pudo conectar con el servidor." });
    }
    setBusy(false);
  }

  const tab = (k: Src, label: string) => (
    <button type="button" className={`tab ${k === "kick" ? "kick" : ""} ${src === k ? "on" : ""}`} onClick={() => setSrc(k)}>{label}</button>
  );

  const editable = live && ((layout === "crop") || (layout === "split"));
  const manual = layout === "crop" ? manualCrop : manualCam;
  const toggleManual = () => (layout === "crop" ? setManualCrop(!manualCrop) : setManualCam(!manualCam));

  return (
    <>
      <div className="hero">
        <h1>Convertí tus streams en <em>clips virales</em></h1>
        <small style={{ color: "var(--muted)" }}>Vertical, con subtítulos y listo para TikTok, Reels y Shorts. En minutos.</small>
      </div>

      <div className="cols">
        {/* IZQUIERDA: fuente */}
        <form className="card" onSubmit={submit}>
          <h3 style={{ fontSize: 13, color: "var(--muted)", letterSpacing: ".08em", marginBottom: 16 }}>VIDEO ORIGINAL</h3>
          <div className="tabs3">{tab("kick", "KICK")}{tab("twitch", "Twitch")}{tab("archivo", "Archivo")}</div>
          <label style={{ textAlign: "center", textTransform: "none", fontSize: 15, color: "var(--text)", fontWeight: 600 }}>
            {src === "archivo" ? "Pega el link del video" : "Pegá el link del stream"}
          </label>
          <div className="pasterow">
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={PH[src]} />
            <button type="button" className="btn ghost sm" onClick={paste}>Pegar</button>
          </div>
          <small style={{ display: "block", textAlign: "center", color: "var(--muted)", margin: "8px 0 16px" }}>Ejemplo: twitch.tv/videos/123456789, un clip o un link de YouTube</small>

          <div className="row" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            <div><label>Desde</label><input value={from} onChange={(e) => setFrom(e.target.value)} placeholder="0:00" /></div>
            <div><label>Hasta</label><input value={to} onChange={(e) => setTo(e.target.value)} placeholder="1:00" /></div>
            <div><label>Duración</label><select name="secs" defaultValue="45"><option value="30">30 s</option><option value="45">45 s</option><option value="60">60 s</option><option value="75">75 s</option><option value="90">90 s</option></select></div>
            <div><label>Cantidad</label><select name="count" defaultValue="5"><option>1</option><option>3</option><option>5</option><option>10</option><option>15</option><option>20</option><option>30</option><option>50</option></select></div>
          </div>
          <div className="row" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div><label>Calidad</label><select name="quality" defaultValue="1080p"><option value="720p">720p</option><option value="1080p">1080p</option><option value="1440p">1440p (2K)</option><option value="2160p">2160p (4K)</option></select></div>
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

        {/* CENTRO: teléfono + editor */}
        <div className="card neon" style={{ padding: 0, overflow: "hidden" }}>
          <h3 style={{ padding: "16px 20px", fontSize: 15, color: "#b79bff", borderBottom: "1px solid var(--line)" }}>📱 ASÍ SE VEN TUS CLIPS</h3>
          <div style={{ padding: 20 }}>
            <PhonePreview layout={layout} embed={embed} cropBox={previewCrop} camBox={previewCam} />

            {!live && (
              <small style={{ display: "block", textAlign: "center", color: "var(--muted)", margin: "14px 0 0" }}>
                {url
                  ? isKick
                    ? "Kick no permite mostrar el video aquí. Los clips se generan igual y el encuadre lo decide la IA."
                    : "No puedo mostrar este link en la vista previa. Los clips se generan igual."
                  : "Pega un link de YouTube, Twitch o un .mp4 y verás aquí tu video con el encuadre elegido."}
              </small>
            )}

            {layout === "duo" && (
              <small style={{ display: "block", textAlign: "center", color: "var(--muted)", margin: "14px 0 0" }}>
                La IA busca a las dos personas sola: la de la izquierda va arriba y la de la derecha abajo (si una está sobre la otra, la de más arriba va arriba). La vista previa es aproximada. Si no las ve claras, usa la mitad izquierda y la mitad derecha del video.
              </small>
            )}

            {editable && (
              <div style={{ marginTop: 16 }}>
                <small style={{ display: "block", color: "var(--muted)", marginBottom: 8, textAlign: "center" }}>
                  {layout === "crop"
                    ? manual ? "Arrastra el recuadro para elegir qué parte se ve en vertical." : "La IA sigue a la persona que habla."
                    : manual ? "Arrastra el recuadro sobre tu cámara (esquina para agrandar). Arriba va la cámara y abajo el juego." : "La IA buscará tu cara para el panel de arriba."}
                </small>
                {manual && (
                  layout === "crop"
                    ? <CropPreview embed={embed} box={cropBox} aspect={ASPECT_VERT} onChange={setCropBox} />
                    : <CropPreview embed={embed} box={camBox} aspect={ASPECT_CAM} onChange={setCamBox} />
                )}
                <button type="button" className="btn ghost sm" style={{ width: "100%", marginTop: 10 }} onClick={toggleManual}>
                  {manual ? (layout === "crop" ? "Usar encuadre automático" : "Que la IA busque mi cámara") : (layout === "crop" ? "Ajustar encuadre a mano" : "Marcar mi cámara a mano")}
                </button>
              </div>
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
            <b>Paso 1:</b> pegá un link de Twitch, YouTube o Kick. Después elegís cómo se ve en el teléfono: vertical, dividido (cámara arriba, juego abajo) o con fondo difuminado.
          </div>
          {stats && <div className="stat" style={{ marginTop: 18 }}><div className="ic">👥</div><div><b>{stats.users.toLocaleString("es")}</b><span>Usuarios registrados</span></div></div>}
          <h3 style={{ fontSize: 14, margin: "26px 0 10px" }}>Últimos clips de la comunidad</h3>
          <CommunityFeed kind="feed" limit={8} />
        </div>
      </div>
    </>
  );
}
