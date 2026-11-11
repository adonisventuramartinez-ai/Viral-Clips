"use client";
import { useEffect, useState } from "react";
import { postHub, useHub } from "@/lib/useHub";

type Row = { id: string; platform: string; handle: string };
const P: [string, string, string][] = [["tiktok", "TikTok", "https://www.tiktok.com/@"], ["instagram", "Instagram", "https://www.instagram.com/"], ["youtube", "YouTube Shorts", "https://www.youtube.com/@"]];

export default function Redes() {
  const [name, setName] = useState("");
  useEffect(() => { try { setName(localStorage.getItem("cf_clipper") || ""); } catch {} }, []);
  const { items, reload } = useHub<Row>("socials", name ? `?clipper=${encodeURIComponent(name)}` : "?clipper=__none__");
  const [msg, setMsg] = useState("");

  async function save(e: React.FormEvent<HTMLFormElement>, platform: string) {
    e.preventDefault();
    const handle = String(new FormData(e.currentTarget).get("handle") || "");
    if (!name.trim()) return setMsg("Primero pon tu nombre abajo.");
    try { localStorage.setItem("cf_clipper", name.trim()); } catch {}
    const err = await postHub("socials", { clipper: name.trim(), platform, handle });
    setMsg(err ?? "Guardado ✔"); reload();
  }
  return (
    <>
      <h1>🔗 Mis redes</h1>
      <p className="sub">Guarda tus cuentas donde publicas. (La publicación automática con OAuth es el siguiente paso; por ahora descargas el clip y lo subes.)</p>
      <div className="card" style={{ maxWidth: 520, marginBottom: 16 }}>
        <label style={{ marginTop: 0 }}>Tu nombre de clipeador</label>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} placeholder="ej. Juan" />
      </div>
      <div className="grid3">
        {P.map(([k, label, base]) => {
          const cur = items?.find((i) => i.platform === k);
          return (
            <form className="card" key={k} onSubmit={(e) => save(e, k)}>
              <b>{label}</b>
              {cur && <div style={{ margin: "6px 0" }}><a className="viral" href={base + cur.handle} target="_blank" rel="noreferrer">@{cur.handle}</a></div>}
              <label>Usuario</label><input name="handle" placeholder="@tuusuario" defaultValue={cur?.handle} />
              <button className="btn sm" style={{ marginTop: 12 }}>Guardar</button>
            </form>
          );
        })}
      </div>
      {msg && <div className="banner ok" style={{ marginTop: 16 }}>{msg}</div>}
    </>
  );
}
