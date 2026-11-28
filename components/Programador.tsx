"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { supabaseBrowser, BUCKET } from "@/lib/supabaseClient";
import { TipoContenido, validarArchivo } from "@/lib/facebook";
import FileDropzone from "./FileDropzone";

interface Theme {
  cardBg: string;
  formBg: string;
  border: string;
  text: string;
  subtext: string;
  accent: string;
  accentBg: string;
}

interface Cuenta {
  id: number;
  nombre: string;
}

interface PaginaCuenta {
  id: string;
  name: string;
  category?: string;
}

interface PostProgramado {
  id: number;
  paginas: { id: string; name: string }[];
  tipo: string;
  titulo: string | null;
  mensaje: string | null;
  archivo_nombre: string | null;
  fecha_programada: string;
  recurrencia: string;
  estado: string;
  intentos: number;
}

interface ProgramadorProps {
  theme: Theme;
}

export default function Programador({ theme }: ProgramadorProps) {
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [cuentaId, setCuentaId] = useState<number | null>(null);
  const [paginasCuenta, setPaginasCuenta] = useState<PaginaCuenta[]>([]);
  const [seleccionadas, setSeleccionadas] = useState<Set<string>>(new Set());
  const [cargandoPaginas, setCargandoPaginas] = useState(false);

  const [tipo, setTipo] = useState<TipoContenido>("foto");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [titulo, setTitulo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [fechaHora, setFechaHora] = useState("");
  const [recurrencia, setRecurrencia] = useState<"ninguna" | "diaria" | "semanal">("ninguna");
  const [programando, setProgramando] = useState(false);

  const [posts, setPosts] = useState<PostProgramado[]>([]);
  const [cargandoPosts, setCargandoPosts] = useState(true);

  useEffect(() => {
    fetch("/api/fb/accounts")
      .then((r) => r.json())
      .then((d) => setCuentas(d.cuentas || []))
      .catch(() => toast.error("No se pudieron cargar las cuentas de Facebook"));
    cargarPosts();
  }, []);

  async function cargarPosts() {
    setCargandoPosts(true);
    try {
      const res = await fetch("/api/fb/schedule");
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "No se pudo cargar la cola");
      setPosts(data.posts || []);
    } catch {
      toast.error("Sin conexión con el servidor");
    } finally {
      setCargandoPosts(false);
    }
  }

  useEffect(() => {
    if (!cuentaId) {
      setPaginasCuenta([]);
      return;
    }
    setCargandoPaginas(true);
    setSeleccionadas(new Set());
    fetch(`/api/fb/accounts/${cuentaId}/paginas`)
      .then((r) => r.json())
      .then((d) => {
        if (d.error) {
          toast.error(d.error);
          setPaginasCuenta([]);
        } else {
          setPaginasCuenta(d.paginas || []);
        }
      })
      .catch(() => toast.error("No se pudieron cargar las páginas"))
      .finally(() => setCargandoPaginas(false));
  }, [cuentaId]);

  function toggleSeleccion(id: string) {
    const nueva = new Set(seleccionadas);
    if (nueva.has(id)) nueva.delete(id);
    else nueva.add(id);
    setSeleccionadas(nueva);
  }

  async function programar() {
    if (!cuentaId) return toast.error("Selecciona una cuenta");
    if (seleccionadas.size === 0) return toast.error("Selecciona al menos una página");
    if (!archivo) return toast.error("Selecciona un archivo");
    if (!fechaHora) return toast.error("Elige fecha y hora");

    const fecha = new Date(fechaHora);
    if (fecha.getTime() <= Date.now()) {
      return toast.error("La fecha debe ser en el futuro");
    }

    setProgramando(true);
    try {
      // 1) Pedir URL firmada de subida
      const prepRes = await fetch("/api/fb/subir-archivo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombreArchivo: archivo.name }),
      });
      const prep = await prepRes.json();
      if (prep.error) throw new Error(prep.error);

      // 2) Subir el archivo directo a Supabase Storage (no pasa por Vercel)
      const { error: uploadError } = await supabaseBrowser.storage
        .from(BUCKET)
        .uploadToSignedUrl(prep.path, prep.token, archivo);
      if (uploadError) throw uploadError;

      // 3) Crear el registro de programación
      const paginasSeleccionadas = paginasCuenta
        .filter((p) => seleccionadas.has(p.id))
        .map((p) => ({ id: p.id, name: p.name }));

      const res = await fetch("/api/fb/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cuenta_id: cuentaId,
          paginas: paginasSeleccionadas,
          tipo,
          titulo,
          mensaje,
          archivo_url: prep.path,
          archivo_nombre: archivo.name,
          fecha_programada: fecha.toISOString(),
          recurrencia,
        }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      toast.success("Publicación programada");
      setArchivo(null);
      setTitulo("");
      setMensaje("");
      setFechaHora("");
      setSeleccionadas(new Set());
      cargarPosts();
    } catch (err: any) {
      toast.error(err.message || "Error al programar");
    } finally {
      setProgramando(false);
    }
  }

  async function cancelar(id: number) {
    if (!confirm("¿Cancelar esta publicación programada?")) return;
    try {
      const res = await fetch(`/api/fb/schedule/${id}`, { method: "DELETE" });
      const d = await res.json().catch(() => ({}));
      if (res.ok) {
        toast.success("Cancelada");
        cargarPosts();
      } else {
        toast.error(d.error || "Error al cancelar");
      }
    } catch {
      toast.error("Sin conexión con el servidor");
    }
  }

  function tiempoRestante(fechaISO: string): string {
    const diff = new Date(fechaISO).getTime() - Date.now();
    if (diff <= 0) return "Publicando pronto...";
    const horas = Math.floor(diff / (1000 * 60 * 60));
    const dias = Math.floor(horas / 24);
    if (dias > 0) return `en ${dias}d ${horas % 24}h`;
    const minutos = Math.floor(diff / (1000 * 60));
    if (horas > 0) return `en ${horas}h ${minutos % 60}m`;
    return `en ${minutos}m`;
  }

  const badgeColor: Record<string, string> = {
    pendiente: "#b45309",
    publicando: "#1a73e8",
    completado: "#1e7e34",
    error: "#c62828",
    cancelado: "#5f6368",
  };
  const badgeBg: Record<string, string> = {
    pendiente: "#fff4e5",
    publicando: "#e8f0fe",
    completado: "#e6f4ea",
    error: "#fce8e6",
    cancelado: "#f1f3f4",
  };

  return (
    <div>
      {/* Formulario nuevo */}
      <div
        style={{
          background: theme.formBg,
          padding: "20px",
          borderRadius: "8px",
          border: `1px solid ${theme.border}`,
          marginBottom: "24px",
        }}
      >
        <h3 style={{ fontSize: "16px", fontWeight: 500, margin: "0 0 16px 0", color: theme.text }}>
          🗓️ Nueva publicación programada
        </h3>

        <div style={{ marginBottom: "12px" }}>
          <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
            Cuenta de Facebook
          </label>
          <select
            value={cuentaId ?? ""}
            onChange={(e) => setCuentaId(e.target.value ? Number(e.target.value) : null)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "6px",
              border: `1px solid ${theme.border}`,
              fontSize: "14px",
              background: theme.cardBg,
              color: theme.text,
            }}
          >
            <option value="">Selecciona una cuenta...</option>
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
          {cuentas.length === 0 && (
            <p style={{ fontSize: "12px", color: theme.subtext, marginTop: "4px" }}>
              No tienes cuentas guardadas. Ve a la pestaña "Cuentas" primero.
            </p>
          )}
        </div>

        {cuentaId && (
          <div style={{ marginBottom: "12px" }}>
            <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
              Páginas
            </label>
            {cargandoPaginas ? (
              <div style={{ fontSize: "13px", color: theme.subtext }}>Cargando páginas...</div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "6px" }}>
                {paginasCuenta.map((p) => (
                  <label
                    key={p.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      padding: "8px 10px",
                      background: seleccionadas.has(p.id) ? theme.accentBg : theme.cardBg,
                      border: `1px solid ${seleccionadas.has(p.id) ? theme.accent : theme.border}`,
                      borderRadius: "6px",
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={seleccionadas.has(p.id)}
                      onChange={() => toggleSeleccion(p.id)}
                      style={{ marginRight: "6px" }}
                    />
                    <span style={{ color: theme.text }}>{p.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "12px", marginBottom: "12px" }}>
          <div>
            <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
              Tipo
            </label>
            <select
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value as TipoContenido);
                setArchivo(null);
              }}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "6px",
                border: `1px solid ${theme.border}`,
                fontSize: "14px",
                background: theme.cardBg,
                color: theme.text,
              }}
            >
              <option value="foto">📸 Foto</option>
              <option value="video">🎬 Video</option>
              <option value="reel">📹 Reel</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
              Archivo
            </label>
            <FileDropzone tipo={tipo} archivo={archivo} onFileSelect={setArchivo} theme={theme} />
          </div>
        </div>

        <div style={{ marginBottom: "12px" }}>
          <input
            type="text"
            placeholder="Título (opcional)"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", border: `1px solid ${theme.border}`, fontSize: "14px", background: theme.cardBg, color: theme.text, boxSizing: "border-box" }}
          />
        </div>

        <div style={{ marginBottom: "12px" }}>
          <textarea
            placeholder="Mensaje..."
            value={mensaje}
            onChange={(e) => setMensaje(e.target.value)}
            rows={3}
            style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", border: `1px solid ${theme.border}`, fontSize: "14px", background: theme.cardBg, color: theme.text, boxSizing: "border-box", fontFamily: "inherit", resize: "vertical" }}
          />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
          <div>
            <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
              Fecha y hora
            </label>
            <input
              type="datetime-local"
              value={fechaHora}
              onChange={(e) => setFechaHora(e.target.value)}
              style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", border: `1px solid ${theme.border}`, fontSize: "14px", background: theme.cardBg, color: theme.text, boxSizing: "border-box" }}
            />
          </div>
          <div>
            <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
              Repetir
            </label>
            <select
              value={recurrencia}
              onChange={(e) => setRecurrencia(e.target.value as any)}
              style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", border: `1px solid ${theme.border}`, fontSize: "14px", background: theme.cardBg, color: theme.text }}
            >
              <option value="ninguna">No repetir</option>
              <option value="diaria">Cada día</option>
              <option value="semanal">Cada semana</option>
            </select>
          </div>
        </div>

        <button
          onClick={programar}
          disabled={programando}
          style={{
            width: "100%",
            padding: "12px",
            background: programando ? "#dadce0" : theme.accent,
            color: (theme as any).accentText || "white",
            border: "none",
            borderRadius: "6px",
            fontSize: "15px",
            fontWeight: 600,
            cursor: programando ? "not-allowed" : "pointer",
          }}
        >
          {programando ? "Programando..." : "🗓️ Programar publicación"}
        </button>
      </div>

      {/* Lista de pendientes */}
      <h4 style={{ fontSize: "14px", color: theme.text, marginBottom: "8px" }}>
        📋 Publicaciones programadas ({posts.filter((p) => p.estado === "pendiente").length} pendientes)
      </h4>

      {cargandoPosts ? (
        <div style={{ color: theme.subtext, fontSize: "13px" }}>Cargando...</div>
      ) : posts.length === 0 ? (
        <div style={{ color: theme.subtext, fontSize: "13px", padding: "12px 0" }}>
          No hay publicaciones programadas todavía.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {posts.map((p) => (
            <div
              key={p.id}
              style={{
                padding: "12px 14px",
                background: theme.cardBg,
                border: `1px solid ${theme.border}`,
                borderRadius: "6px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "8px",
              }}
            >
              <div>
                <div style={{ fontSize: "14px", fontWeight: 500, color: theme.text }}>
                  {p.titulo || p.archivo_nombre || "Sin título"}
                </div>
                <div style={{ fontSize: "12px", color: theme.subtext }}>
                  {p.paginas.map((pg) => pg.name).join(", ")} · {new Date(p.fecha_programada).toLocaleString()}
                  {p.estado === "pendiente" && ` · ${tiempoRestante(p.fecha_programada)}`}
                  {p.recurrencia !== "ninguna" && ` · 🔁 ${p.recurrencia}`}
                </div>
              </div>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <span
                  style={{
                    padding: "3px 10px",
                    borderRadius: "12px",
                    fontSize: "12px",
                    background: badgeBg[p.estado] || theme.formBg,
                    color: badgeColor[p.estado] || theme.subtext,
                  }}
                >
                  {p.estado}
                </span>
                {p.estado === "pendiente" && (
                  <button
                    onClick={() => cancelar(p.id)}
                    style={{ background: "none", border: "none", color: "#c62828", fontSize: "12px", cursor: "pointer" }}
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

