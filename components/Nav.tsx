"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  ["/crear", "Crear clips"],
  ["/en-vivo", "En vivo"],
  ["/biblioteca", "Biblioteca"],
  ["/ajustes", "Ajustes de IA"],
  ["/almacenamiento", "Almacenamiento"],
  ["/ayuda", "Ayuda"],
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="top">
      <div className="logo">Clip<b>Forge</b></div>
      <nav className="nav">
        {tabs.map(([href, label]) => (
          <Link key={href} href={href} className={path.startsWith(href) ? "on" : ""}>{label}</Link>
        ))}
      </nav>
    </header>
  );
}
