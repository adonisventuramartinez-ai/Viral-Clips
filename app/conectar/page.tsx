"use client";
import { useCallback, useEffect, useState } from "react";

type Item = { saved: Record<string, string>; updatedAt: string | null };
type Field = { k: string; label: string; ph: string; optional?: boolean };
type Net = { id: string; name: string; icon: string; fields: Field[]; steps: string[]; note?: string };

const NETS: Net[] = [
  {
    id: "facebook", name: "Facebook (Reels)", icon: "📘",
    fields: [
      { k: "page_id", label: "ID de tu página", ph: "123456789012345" },
      { k: "page_token", label: "Token de la página", ph: "EAAB…" },
    ],
    steps: [
      "Entra a developers.facebook.com y crea una app (tipo Empresa). Agrega el producto «Facebook Login para empresas».",
      "Abre Graph API Explorer, elige tu app, pide los permisos pages_show_list, pages_read_engagement, pages_manage_posts y publish_video, y genera el token de usuario.",
      "Con ese token consulta /me/accounts: ahí salen el id de tu página y su access_token (el token de la página). Ese es el que pegas aquí.",
      "Para que no venza, conviértelo en token de larga duración (Herramienta de depuración de tokens > Extender).",
    ],
    note: "El mismo token sirve para leer las estadísticas y, si tu página tiene Instagram enlazado, para Instagram.",
  },
  {
    id: "instagram", name: "Instagram (Reels)", icon: "📸",
    fields: [
      { k: "user_id", label: "ID de la cuenta de Instagram", ph: "17841400000000000" },
      { k: "token", label: "Token (opcional: si lo dejas vacío usa el de Facebook)", ph: "EAAB…", optional: true },
    ],
    steps: [
      "La cuenta debe ser Profesional (Business o Creator) y estar enlazada a tu página de Facebook.",
      "Pide también el permiso instagram_basic e instagram_content_publish en el Graph API Explorer.",
      "Consulta /TU_ID_DE_PAGINA?fields=instagram_business_account: el id que sale es el que pegas aquí.",
    ],
  },
  {
    id: "youtube", name: "YouTube Shorts", icon: "▶️",
    fields: [
      { k: "client_id", label: "Client ID", ph: "123…apps.googleusercontent.com" },
      { k: "client_secret", label: "Client secret", ph: "GOCSPX-…" },
      { k: "refresh_token", label: "Refresh token", ph: "1//0g…" },
      { k: "api_key", label: "API key (opcional, para leer estadísticas)", ph: "AIza…", optional: true },
    ],
    steps: [
      "En console.cloud.google.com crea un proyecto, activa «YouTube Data API v3» y crea credenciales OAuth (tipo aplicación web o de escritorio).",
      "En OAuth Playground (developers.google.com/oauthplayground) usa tu propio Client ID/secret, autoriza el permiso youtube.upload (y youtube.readonly para estadísticas) con la cuenta de tu canal y copia el Refresh token.",
      "Opcional: crea una API key para que Mi página lea las vistas sin permisos extra.",
    ],
    note: "Los proyectos de Google sin auditar suben los videos como PRIVADOS hasta que pasas la auditoría de la API.",
  },
];

const ago = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : null);

export default function Conectar() {
  const [items, setItems] = useState<Record<string, Item>>({});
  const [connected, setConnected] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [open, setOpen] = useState<string>("");

  const load = useCallback(async () => {
    const r = await fetch("/api/conexiones", { cache: "no-store" }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) return setErr(j?.error ?? "No se pudo conectar");
    setErr(""); setItems(j.items ?? {}); setConnected(j.connected ?? []);
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);

  async function save(e: React.FormEvent<HTMLFormElement>, n: Net) {
    e.preventDefault();
    const form = e.currentTarget; const f = new FormData(form);
    const fields: Record<string, string> = {};
    n.fields.forEach((x) => { fields[x.k] = String(f.get(x.k) ?? ""); });
    setBusy(n.id);
    const r = await fetch("/api/conexiones", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ network: n.id, fields }) }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy("");
    setNote((o) => ({ ...o, [n.id]: r?.ok ? (j?.pageInfo?.name ? `Guardado ✔. Página: ${j.pageInfo.name}. El worker lo toma en unos 2 minutos.` : "Guardado ✔. El worker lo toma en unos 2 minutos (sin reiniciar).") : j?.error ?? "No se pudo guardar" }));
    if (r?.ok) form.reset();
    load();
  }
  async function remove(n: Net) {
    if (!confirm(`¿Quitar las llaves de ${n.name}? El worker deja de usarlas al reiniciarlo.`)) return;
    await fetch("/api/conexiones", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ network: n.id }) }).catch(() => null);
    load();
  }

  return (
    <>
      <h1>🔌 Conectar cuentas</h1>
      <p className="sub">Pega aquí las llaves de tus redes y el worker las usa para publicar y leer tus estadísticas. No hace falta tocar el archivo .env.</p>
      {err && <div className="banner">{err}</div>}
      <div style={{ display: "grid", gap: 14 }}>
        {NETS.map((n) => {
          const it = items[n.id];
          const has = it && Object.values(it.saved).some(Boolean);
          const live = connected.includes(n.id);
          return (
            <div key={n.id} className="card">
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {n.id === "facebook" && it?.pagePhoto && <img src={it.pagePhoto} alt="" style={{ width: 40, height: 40, borderRadius: "50%", border: "2px solid var(--glass-border)" }} />}
                  <b style={{ fontSize: 17 }}>{n.icon} {n.id === "facebook" && it?.pageName ? it.pageName : n.name}</b>
                </div>
                <span>{live ? "✅ Conectado (el worker lo está usando)" : has ? "⏳ Guardado: el worker lo toma en unos minutos" : "⚪ Sin conectar"}</span>
              </div>
              {n.id === "facebook" && it?.pageName && <small style={{ color: "var(--muted)", display: "block", marginTop: 4 }}>Página: {it.pageName} · ID: {it.saved?.page_id}</small>}
              {it?.updatedAt && <small style={{ color: "var(--muted)" }}>Última vez guardado: {ago(it.updatedAt)}</small>}
              <form onSubmit={(e) => save(e, n)} style={{ display: "grid", gap: 8, marginTop: 12 }}>
                {n.fields.map((x) => (
                  <label key={x.k} style={{ display: "grid", gap: 4, fontSize: 13 }}>
                    <span>{x.label}{it?.saved[x.k] ? <small style={{ color: "var(--muted)" }}> · guardado: {it.saved[x.k]}</small> : null}</span>
                    <input name={x.k} placeholder={it?.saved[x.k] ? "Déjalo vacío para conservar el actual" : x.ph} autoComplete="off" spellCheck={false} />
                  </label>
                ))}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button className="btn" disabled={busy === n.id}>{busy === n.id ? "Guardando…" : has ? "Actualizar" : "Conectar"}</button>
                  <button type="button" className="btn ghost" onClick={() => setOpen(open === n.id ? "" : n.id)}>{open === n.id ? "Ocultar guía" : "¿De dónde saco esto?"}</button>
                  {has && <button type="button" className="btn ghost" onClick={() => remove(n)}>Quitar</button>}
                </div>
                {note[n.id] && <small style={{ color: note[n.id].startsWith("Guardado") ? "var(--text)" : "#ef4444" }}>{note[n.id]}</small>}
              </form>
              {open === n.id && (
                <div style={{ marginTop: 12, fontSize: 13, color: "var(--muted)" }}>
                  <ol style={{ paddingLeft: 18, display: "grid", gap: 4 }}>{n.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
                  {n.note && <p style={{ marginTop: 8 }}>{n.note}</p>}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p style={{ marginTop: 16, fontSize: 13, color: "var(--muted)" }}>
        Las llaves se guardan en tu Supabase y solo las lee el servidor: esta página nunca vuelve a mostrarlas completas. Ya no hace falta ponerlas en worker/.env, pero si las tienes allí también funcionan.
        Esto es pegar las llaves, no un botón «Iniciar sesión con Facebook»: ese botón necesita una app de Meta y Google ya aprobadas por ellos.
      </p>
    </>
  );
}
