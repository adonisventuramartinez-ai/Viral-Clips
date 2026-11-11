"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const DONATE = process.env.NEXT_PUBLIC_DONATE_URL || "";

export default function Topbar() {
  const path = usePathname();
  const [name, setName] = useState("");
  useEffect(() => {
    try { setName(localStorage.getItem("cf_clipper") || ""); } catch {}
  }, [path]);
  if (path === "/login") return null;
  return (
    <header className="topbar">
      <Link href="/crear" className="logo" style={{ fontWeight: 700, fontSize: 20 }}>⚡ Clip<b>Forge</b></Link>
      <Link href="/promo" className="pill">📣 Publicita tu canal</Link>
      {DONATE && <a href={DONATE} target="_blank" rel="noreferrer" className="pill green">♥ Donar</a>}
      <Link href="/redes" className="pill ghost">👤 {name || "Mi perfil"}</Link>
    </header>
  );
}
