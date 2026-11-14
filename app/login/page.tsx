"use client";
import { useState } from "react";

export default function Login() {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const password = new FormData(e.currentTarget).get("password");
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (res.ok) window.location.href = "/crear";
    else {
      const j = await res.json().catch(() => ({}));
      setErr(j.error || "Contraseña incorrecta");
      setBusy(false);
    }
  }

  return (
    <form className="card neon" onSubmit={submit} style={{ maxWidth: 380, margin: "80px auto" }}>
      <div className="logo" style={{ fontSize: 24 }}>Clip<b>Forge</b></div>
      <label>Contraseña</label>
      <input name="password" type="password" autoFocus />
      <div style={{ marginTop: 16 }}><button className="btn" disabled={busy}>Entrar</button></div>
      {err && <div className="banner" style={{ marginTop: 16, marginBottom: 0 }}>{err}</div>}
    </form>
  );
}
