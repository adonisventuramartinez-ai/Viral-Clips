"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const I = (d: string) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

// [ruta, etiqueta, icono]
const items: [string, string, React.ReactNode][] = [
  ["/crear", "Proyecto", I("M4 5h16v14H4zM4 9h16M9 5v14")],
  ["/top", "Top global", I("M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3")],
  ["/clipeadores", "Clipeadores", I("M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.3 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z")],
  ["/donadores", "Donadores", I("M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.6-7 10-7 10z")],
  ["/estadisticas", "Estadísticas", I("M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3")],
  ["/redes", "Mis redes", I("M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8.6 13.5l6.8 4M15.4 6.5l-6.8 4")],
  ["/promo", "Promo", I("M3 11v3l11 5V6zM14 8l6-3v14l-6-3M6 15l1 5h3")],
  ["/sugerencias", "Sugerencias", I("M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z")],
  ["/programas", "Programas", I("M4 7h16v11H4zM8 3l4 4 4-4")],
  ["/biblioteca", "Biblioteca", I("M5 4h4v16H5zM11 4h4v16h-4zM17 6l3 .8-3.5 13.2-3-.8")],
  ["/en-vivo", "En vivo", I("M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M7.5 7.5a6 6 0 0 0 0 9M16.5 7.5a6 6 0 0 1 0 9M4.5 4.5a10 10 0 0 0 0 15M19.5 4.5a10 10 0 0 1 0 15")],
  ["/ajustes", "Ajustes IA", I("M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12l2-1-2-4-2 1a7 7 0 0 0-2-1l-.5-2h-5L9 8a7 7 0 0 0-2 1L5 8l-2 4 2 1a7 7 0 0 0 0 2l-2 1 2 4 2-1a7 7 0 0 0 2 1l.5 2h5l.5-2a7 7 0 0 0 2-1l2 1 2-4-2-1")],
];

export default function Sidebar() {
  const path = usePathname();
  if (path === "/login") return null;
  return (
    <aside className="side">
      {items.map(([href, label, icon]) => (
        <Link key={href} href={href} className={path.startsWith(href) ? "on" : ""}>
          {icon}
          {label}
        </Link>
      ))}
    </aside>
  );
}
