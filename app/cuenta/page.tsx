"use client";
import { useEffect, useRef, useState } from "react";
import Avatar from "@/components/Avatar";
import { refreshMe, useMe } from "@/lib/useMe";

const SIZE = 256;

/** Achica y recorta la foto al centro en un cuadrado de 256 px (JPEG): así pesa ~20 KB y se guarda en la cuenta. */
function shrink(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const side = Math.min(img.width, img.height);
      const c = document.createElement("canvas");
      c.width = c.height = SIZE;
      const ctx = c.getContext("2d");
      if (!ctx) { URL.revokeObjectURL(url); return reject(new Error("canvas")); }
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, SIZE, SIZE);   // por si la imagen es PNG con transparencia
      ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, SIZE, SIZE);
      URL.revokeObjectURL(url);
      resolve(c.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("img")); };
    img.src = url;
  });
}

export default function Cuenta() {
  const { me, loaded } = useMe();
  const [name, setName] = useState("");
  const [photo, setPhoto] = useState<string | null | undefined>(undefined);   // undefined = sin cambio, null = quitar
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [welcome, setWelcome] = useState(false);
  const file = useRef<HTMLInputElement>(null);

  useEffect(() => { if (me) setName(me.display_name); }, [me]);
  useEffect(() => { setWelcome(new URLSearchParams(window.location.search).get("bienvenido") === "1"); }, []);

  async function patch(body: Record<string, unknown>, okText: string) {
    setBusy(true); setMsg(null);
    const r = await fetch("/api/cuenta", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setBusy(false);
    if (!r?.ok) { setMsg({ ok: false, t: j?.error ?? "No se pudo guardar" }); return false; }
    setMsg({ ok: true, t: okText });
    refreshMe();
    return true;
  }

  async function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (!/^image\//.test(f.type)) return setMsg({ ok: false, t: "Elige una imagen (JPG, PNG o WebP)" });
    try { setPhoto(await shrink(f)); setMsg(null); } catch { setMsg({ ok: false, t: "No pude leer esa imagen. Prueba con otra." }); }
  }

  async function saveProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body: Record<string, unknown> = { display_name: name };
    if (photo !== undefined) body.avatar = photo;
    if (await patch(body, "Guardado ✔")) setPhoto(undefined);
  }

  async function savePassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    if (f.get("new_password") !== f.get("new_password2")) return setMsg({ ok: false, t: "Las contraseñas nuevas no son iguales" });
    if (await patch({ current_password: f.get("current_password"), new_password: f.get("new_password") }, "Contraseña cambiada ✔")) form.reset();
  }

  async function logout() {
    await fetch("/api/logout", { method: "POST" }).catch(() => null);
    window.location.href = "/login";
  }

  if (!loaded) return <p className="sub">Cargando…</p>;
  if (!me) {
    return (
      <>
        <h1>👤 Mi cuenta</h1>
        <div className="card" style={{ maxWidth: 520 }}>
          <p>Ahora mismo entraste solo con la clave de acceso, sin cuenta. Crea tu cuenta para tener tu nombre y tu foto de perfil, y que la sesión se quede guardada.</p>
          <div style={{ marginTop: 14 }}><a className="btn" href="/login?crear=1" style={{ display: "inline-block" }}>Crear mi cuenta</a></div>
        </div>
      </>
    );
  }

  const shown = photo === undefined ? me.avatar : photo;
  return (
    <>
      <h1>👤 Mi cuenta</h1>
      <p className="sub">Tu nombre y tu foto se ven arriba en toda la app.</p>
      {welcome && <div className="banner ok">¡Cuenta creada! Pon tu foto de perfil aquí abajo si quieres.</div>}
      {msg && <div className={`banner ${msg.ok ? "ok" : ""}`}>{msg.t}</div>}

      <form className="card" onSubmit={saveProfile} style={{ maxWidth: 520, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <Avatar name={name || me.display_name} src={shown} size={96} />
          <div style={{ display: "grid", gap: 8 }}>
            <input ref={file} type="file" accept="image/*" onChange={pick} style={{ display: "none" }} />
            <button type="button" className="btn sm" onClick={() => file.current?.click()}>📷 {shown ? "Cambiar foto" : "Subir foto"}</button>
            {shown && <button type="button" className="btn sm ghost" onClick={() => setPhoto(null)}>Quitar foto</button>}
            {photo !== undefined && <small style={{ color: "var(--muted)" }}>{photo === null ? "Se quitará al guardar." : "Foto nueva: falta guardar."}</small>}
          </div>
        </div>
        <label>Tu nombre</label>
        <input value={name} onChange={(e) => setName(e.target.value)} minLength={2} maxLength={40} required />
        <label>Usuario</label>
        <input value={`@${me.username}`} disabled />
        <div style={{ marginTop: 16 }}><button className="btn" disabled={busy}>{busy ? "Guardando…" : "Guardar"}</button></div>
      </form>

      <form className="card" onSubmit={savePassword} style={{ maxWidth: 520, marginBottom: 16 }}>
        <b>Cambiar contraseña</b>
        <label>Contraseña actual</label>
        <input name="current_password" type="password" required autoComplete="current-password" />
        <label>Contraseña nueva (mínimo 8)</label>
        <input name="new_password" type="password" required minLength={8} maxLength={100} autoComplete="new-password" />
        <label>Repite la contraseña nueva</label>
        <input name="new_password2" type="password" required minLength={8} maxLength={100} autoComplete="new-password" />
        <div style={{ marginTop: 16 }}><button className="btn" disabled={busy}>Cambiar contraseña</button></div>
      </form>

      <button type="button" className="btn ghost" onClick={logout}>↩ Salir</button>
    </>
  );
}
