"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { COLOR_ESTADO, ETIQUETA_ESTADO, ICONO_TIPO, tiempoRelativo } from "@/lib/estados";

interface Theme { cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string }

interface Post {
  id: number; paginas: { id: string; name: string }[]; tipo: string; titulo: string | null;
  archivo_nombre: string | null; fecha_programada: string; estado: string; intentos: number; ultimo_error: string | null;
}

const FILTROS = ["pendiente", "publicando", "error", "completado", "cancelado", "todos"] as const;

export default function Cola({ theme }: { theme: Theme }) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [cargando, setCargando] = useState(true);
  const [filtro, setFiltro] = useState<(typeof FILTROS)[number]>("pendiente");

  async function cargar() {
    try {
      const r = await fetch("/api/fb/schedule");
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.error || "No se pudo cargar la cola");
      setPosts(d.posts || []);
    } catch (e: any) {
      toast.error(e?.message || "Sin conexión con el servidor");
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 30_000);
    return () => clearInterval(t);
  }, []);

  async function cancelar(id: number) {
    if (!confirm("¿Cancelar esta publicación?")) return;
    try {
      const r = await fetch(`/api/fb/schedule/${id}`, { method: "DELETE" });
      const d = await r.json().catch(() => ({}));
      r.ok ? toast.success("Cancelada") : toast.error(d.error || "No se pudo cancelar");
    } catch {
      toast.error("Sin conexión con el servidor");
    }
    cargar();
  }

  async function reintentar(id: number) {
    try {
      const r = await fetch(`/api/fb/schedule/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accion: "reintentar" }),
      });
      const d = await r.json().catch(() => ({}));
      r.ok ? toast.success("Volvió a la cola") : toast.error(d.error || "No se pudo reintentar");
    } catch {
      toast.error("Sin conexión con el servidor");
    }
    cargar();
  }

  const cuenta = (f: string) => (f === "todos" ? posts.length : posts.filter((p) => p.estado === f).length);
  const lista = posts
    .filter((p) => filtro === "todos" || p.estado === filtro)
    .sort((a, b) =>
      filtro === "completado" || filtro === "todos"
        ? new Date(b.fecha_programada).getTime() - new Date(a.fecha_programada).getTime()
        : new Date(a.fecha_programada).getTime() - new Date(b.fecha_programada).getTime()
    );

  const boton = { background: "none", border: `1px solid ${theme.border}`, color: theme.text, borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: 12 } as const;

  return (
    <div style={{ color: theme.text }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        {FILTROS.map((f) => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            style={{
              padding: "6px 12px", borderRadius: 16, fontSize: 13, cursor: "pointer",
              border: `1px solid ${filtro === f ? theme.accent : theme.border}`,
              background: filtro === f ? theme.accentBg : "transparent",
              color: filtro === f ? theme.accent : theme.subtext,
            }}
          >
            {f === "todos" ? "Todos" : ETIQUETA_ESTADO[f]} ({cuenta(f)})
          </button>
        ))}
      </div>

      {cargando && <p style={{ color: theme.subtext }}>Cargando…</p>}
      {!cargando && lista.length === 0 && <p style={{ color: theme.subtext }}>No hay publicaciones en esta lista.</p>}

      {lista.map((p) => (
        <div key={p.id} style={{ background: theme.formBg, border: `1px solid ${theme.border}`, borderLeft: `4px solid ${COLOR_ESTADO[p.estado] || theme.border}`, borderRadius: 8, padding: 12, marginBottom: 8 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <span>{ICONO_TIPO[p.tipo] || "📄"}</span>
            <div style={{ flex: 1, minWidth: 160 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{p.titulo || p.archivo_nombre || "Sin título"}</div>
              <div style={{ fontSize: 12, color: theme.subtext }}>
                {p.paginas.map((x) => x.name).join(", ")} · {new Date(p.fecha_programada).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} ({tiempoRelativo(p.fecha_programada)})
              </div>
            </div>
            <span style={{ fontSize: 12, color: COLOR_ESTADO[p.estado], fontWeight: 600 }}>{ETIQUETA_ESTADO[p.estado] || p.estado}</span>
            {p.estado === "error" && <button style={boton} onClick={() => reintentar(p.id)}>↻ Reintentar</button>}
            {(p.estado === "pendiente" || p.estado === "error") && <button style={boton} onClick={() => cancelar(p.id)}>Cancelar</button>}
          </div>
          {p.ultimo_error && p.estado !== "completado" && (
            <div style={{ fontSize: 12, color: "#ef4444", marginTop: 6, wordBreak: "break-word" }}>
              {p.intentos > 0 && `Intento ${p.intentos}: `}{p.ultimo_error}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

