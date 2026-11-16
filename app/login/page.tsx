"use client";
import { useEffect, useState } from "react";

type Mode = "entrar" | "crear" | "clave";

export default function Login() {
  const [mode, setMode] = useState<Mode>("entrar");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  // /login?crear=1 abre directo la pestaña de crear cuenta (se lee aquí para no necesitar Suspense en el build)
  useEffect(() => { if (new URLSearchParams(window.location.search).get("crear")) setMode("crear"); }, []);

  async function send(url: string, body: Record<string, unknown>, goTo: string) {
    setBusy(true); setErr("");
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => null);
    if (res?.ok) { window.location.href = goTo; return; }
    const j = await res?.json().catch(() => ({}));
    setErr(j?.error || "No se pudo conectar. Intenta otra vez.");
    setBusy(false);
  }

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => String(f.get(k) ?? "");
    if (mode === "entrar") return send("/api/login", { username: v("username"), password: v("password") }, "/crear");
    if (mode === "clave") return send("/api/login", { password: v("password") }, "/crear");
    if (v("password") !== v("password2")) return setErr("Las contraseñas no son iguales");
    return send("/api/registro", { display_name: v("display_name"), username: v("username"), password: v("password"), code: v("code") }, "/cuenta?bienvenido=1");
  }

  const tab = (m: Mode, label: string) => (
    <button type="button" className={`tab ${mode === m ? "on" : ""}`} onClick={() => { setMode(m); setErr(""); }}>{label}</button>
  );

  return (
    <form className="card neon" onSubmit={submit} style={{ maxWidth: 420, margin: "60px auto" }}>
      <div className="logo" style={{ fontSize: 24, marginBottom: 14 }}>Clip<b>Forge</b></div>
      {mode !== "clave" && <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6 }}>{tab("entrar", "Entrar")}{tab("crear", "Crear cuenta")}</div>}

      {mode === "crear" && (
        <>
          <label>Tu nombre</label>
          <input name="display_name" required minLength={2} maxLength={40} placeholder="ej. Juan Pérez" autoComplete="name" autoFocus />
        </>
      )}
      {mode !== "clave" && (
        <>
          <label>Usuario</label>
          <input name="username" required minLength={3} maxLength={25} placeholder="ej. juanp" autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus={mode === "entrar"} />
          {mode === "crear" && <small style={{ color: "var(--muted)" }}>Minúsculas, números, punto o guion bajo (3 a 24).</small>}
        </>
      )}

      <label>{mode === "clave" ? "Clave de acceso" : "Contraseña"}</label>
      <input name="password" type="password" required minLength={mode === "entrar" || mode === "clave" ? 1 : 8} maxLength={100} autoComplete={mode === "crear" ? "new-password" : "current-password"} autoFocus={mode === "clave"} />
      {mode === "crear" && (
        <>
          <small style={{ color: "var(--muted)" }}>Mínimo 8 caracteres.</small>
          <label>Repite la contraseña</label>
          <input name="password2" type="password" required minLength={8} maxLength={100} autoComplete="new-password" />
          <label>Código de acceso</label>
          <input name="code" type="password" required autoComplete="off" />
          <small style={{ color: "var(--muted)" }}>Es la clave de acceso de la app (APP_PASSWORD). Pídesela a quien la administra.</small>
        </>
      )}

      <div style={{ marginTop: 16 }}>
        <button className="btn" disabled={busy} style={{ width: "100%" }}>{busy ? "Un momento…" : mode === "crear" ? "Crear mi cuenta" : "Entrar"}</button>
      </div>
      {err && <div className="banner" style={{ marginTop: 16, marginBottom: 0 }}>{err}</div>}

      <div style={{ marginTop: 14, textAlign: "center" }}>
        {mode === "clave"
          ? <button type="button" className="btn sm ghost" onClick={() => { setMode("entrar"); setErr(""); }}>← Entrar con mi cuenta</button>
          : <button type="button" className="btn sm ghost" onClick={() => { setMode("clave"); setErr(""); }}>Entrar solo con la clave de acceso</button>}
      </div>
    </form>
  );
}
