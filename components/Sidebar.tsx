"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const I = (d: string) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

// [ruta, etiqueta, icono]
const items: [string, string, React.ReactNode][] = [
  ["/crear", "Proyecto", I("M4 5h16v14H4zM4 9h16M9 5v14")],
  ["/viral", "Hacerlo viral", I("M12 3c1 3 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 1-9z")],
  ["/mi-pagina", "Mi página", I("M3 12l4-4 4 4 5-6 5 6M3 20h18")],
  ["/estadisticas", "Retención", I("M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3")],
  ["/conectar", "Conectar cuentas", I("M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0zM12 16v5")],
  ["/programas", "Programas", I("M4 7h16v11H4zM8 3l4 4 4-4")],
  ["/auto", "Clips automáticos", I("M13 2L4 14h7l-1 8 9-12h-7z")],
  ["/cola", "Cola", I("M8 6h12M8 12h12M8 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01")],
  ["/biblioteca", "Biblioteca", I("M5 4h4v16H5zM11 4h4v16h-4zM17 6l3 .8-3.5 13.2-3-.8")],
  ["/resumen", "Crear resumen", I("M4 4h16v16H4zM8 8h8M8 12h8M8 16h5")],
  ["/en-vivo", "En vivo", I("M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M7.5 7.5a6 6 0 0 0 0 9M16.5 7.5a6 6 0 0 1 0 9M4.5 4.5a10 10 0 0 0 0 15M19.5 4.5a10 10 0 0 1 0 15")],
  ["/ajustes", "Ajustes IA", I("M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12l2-1-2-4-2 1a7 7 0 0 0-2-1l-.5-2h-5L9 8a7 7 0 0 0-2 1L5 8l-2 4 2 1a7 7 0 0 0 0 2l-2 1 2 4 2-1a7 7 0 0 0 2 1l.5 2h5l.5-2a7 7 0 0 0 2-1l2 1 2-4-2-1")],
];

export default function Sidebar() {
  const path = usePathname();
  if (path === "/login") return null;
  return (
    <aside className="side">
      <div style={{ textAlign: "center", padding: "8px 0 12px", borderBottom: "1px solid var(--glass-border)", marginBottom: 8 }}>
        <div style={{ fontSize: 22, fontWeight: 800, background: "var(--grad)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text", letterSpacing: "-0.03em" }}>CF</div>
        <div style={{ fontSize: 9, color: "var(--muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 2 }}>ClipForge</div>
      </div>
      {items.map(([href, label, icon]) => (
        <Link key={href} href={href} className={path.startsWith(href) ? "on" : ""}>
          {icon}
          {label}
        </Link>
      ))}
    </aside>
  );
}
