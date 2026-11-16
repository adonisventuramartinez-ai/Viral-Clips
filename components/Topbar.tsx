"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Avatar from "@/components/Avatar";
import { useMe } from "@/lib/useMe";

const DONATE = process.env.NEXT_PUBLIC_DONATE_URL || "";

export default function Topbar() {
  const path = usePathname();
  const { me, loaded } = useMe();
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => { setOpen(false); }, [path]);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("cf_clipper") || "";
      // Las páginas que ya existían (Mis redes, Estadísticas, En vivo…) usan este nombre: con cuenta se llena solo la primera vez.
      if (me && !saved) localStorage.setItem("cf_clipper", me.display_name);
      setName(saved || me?.display_name || "");
    } catch {}
  }, [path, me]);

  async function logout() {
    await fetch("/api/logout", { method: "POST" }).catch(() => null);
    window.location.href = "/login";
  }

  if (path === "/login") return null;
  const item = { display: "block", padding: "10px 14px", fontSize: 14, color: "var(--text)", background: "transparent", border: 0, width: "100%", textAlign: "left" as const, font: "inherit", cursor: "pointer" };
  return (
    <header className="topbar">
      <Link href="/crear" className="logo" style={{ fontWeight: 700, fontSize: 20 }}>⚡ Clip<b>Forge</b></Link>
      {DONATE && <a href={DONATE} target="_blank" rel="noreferrer" className="pill green">♥ Donar</a>}
      {me ? (
        <div style={{ position: "relative" }}>
          <button type="button" className="pill ghost" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} style={{ padding: "4px 14px 4px 4px" }}>
            <Avatar name={me.display_name} src={me.avatar} size={32} />
            {me.display_name}
          </button>
          {open && (
            <>
              <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
              <div role="menu" style={{ position: "absolute", right: 0, top: "calc(100% + 8px)", zIndex: 50, minWidth: 210, background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 14, overflow: "hidden", boxShadow: "0 10px 30px rgba(0,0,0,.45)" }}>
                <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)" }}>
                  <b>{me.display_name}</b>
                  <div><small style={{ color: "var(--muted)" }}>@{me.username}</small></div>
                </div>
                <Link href="/cuenta" role="menuitem" style={item}>👤 Mi cuenta y foto</Link>
                <Link href="/redes" role="menuitem" style={item}>🔗 Mis redes</Link>
                <button type="button" role="menuitem" onClick={logout} style={{ ...item, borderTop: "1px solid var(--line)", color: "#ff6b8f" }}>↩ Salir</button>
              </div>
            </>
          )}
        </div>
      ) : loaded ? (
        <Link href="/login?crear=1" className="pill ghost">👤 {name || "Crear mi cuenta"}</Link>
      ) : null}
    </header>
  );
}
