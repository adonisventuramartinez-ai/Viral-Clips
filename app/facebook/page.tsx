"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  obtenerPaginas,
  publicarContenido,
  getLoginUrl,
  FacebookPage,
  TipoContenido,
} from "@/lib/facebook";
import Dashboard from "@/components/Dashboard";
import Metricas from "@/components/Metricas";
import FileDropzone from "@/components/FileDropzone";
import PreviewModal from "@/components/PreviewModal";
import AccesoGate from "@/components/AccesoGate";
import CuentasManager from "@/components/CuentasManager";
import Programador from "@/components/Programador";
import Lote from "@/components/Lote";
import TikTok from "@/components/TikTok";
import Sidebar, { Seccion } from "@/components/FBSidebar";
import Eliminador from "@/components/Eliminador";
import Inicio from "@/components/Inicio";
import Cola from "@/components/Cola";
import Calendario from "@/components/Calendario";

interface Resultado {
  pagina: string;
  exito: boolean;
  mensaje: string;
}

interface PublicacionHistorial {
  id: string;
  fecha: string;
  tipo: string;
  titulo: string;
  mensaje: string;
  paginas: number;
  exitos: number;
  errores: number;
  resultados: Resultado[];
}

const THEME_LIGHT = {
  bg: "#f0f2f5",
  cardBg: "#ffffff",
  formBg: "#f8f9fa",
  border: "#e0e0e0",
  text: "#1a1a1a",
  subtext: "#5f6368",
  accent: "#1a73e8",
  accentBg: "#e8f0fe",
  accentText: "white",
};

const THEME_DARK = {
  bg: "#08090a",
  cardBg: "#111413",
  formBg: "#0d100f",
  border: "#232826",
  text: "#e9efe9",
  subtext: "#8a948d",
  accent: "#b6ff3c",
  accentBg: "#1b2610",
  accentText: "#0b0f06",
};

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [paginas, setPaginas] = useState<FacebookPage[]>([]);
  const [seleccionadas, setSeleccionadas] = useState<Set<string>>(new Set());
  const [tipo, setTipo] = useState<TipoContenido>("foto");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [titulo, setTitulo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [publicando, setPublicando] = useState(false);
  const [progresoPorPagina, setProgresoPorPagina] = useState<{ [id: string]: number }>({});
  const [resultados, setResultados] = useState<Resultado[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cargandoPaginas, setCargandoPaginas] = useState(false);
  const [historial, setHistorial] = useState<PublicacionHistorial[]>([]);
  const [tabActivo, setTabActivo] = useState<Seccion>("inicio");
  const [modoOscuro, setModoOscuro] = useState(false);
  const [previewAbierto, setPreviewAbierto] = useState(false);

  const theme = modoOscuro ? THEME_DARK : THEME_LIGHT;

  useEffect(() => {
    const guardado = localStorage.getItem("modo_oscuro");
    if (guardado !== null) {
      setModoOscuro(guardado === "true");
    } else {
      setModoOscuro(true); // el panel nuevo es oscuro por defecto
    }

    const hash = window.location.hash;
    if (hash.startsWith("#token=")) {
      const t = decodeURIComponent(hash.replace("#token=", ""));
      setToken(t);
      localStorage.setItem("fb_token", t);
      window.history.replaceState(null, "", window.location.pathname);
    } else {
      const guardadoToken = localStorage.getItem("fb_token");
      if (guardadoToken) setToken(guardadoToken);
    }

    const params = new URLSearchParams(window.location.search);
    const err = params.get("error");
    if (err) {
      setError(err);
      toast.error(err);
    }
  }, []);

  useEffect(() => {
    const guardado = localStorage.getItem("historial_publicaciones");
    if (guardado) {
      try {
        setHistorial(JSON.parse(guardado));
      } catch (e) {
        console.error("Error al cargar historial:", e);
      }
    }
  }, []);

  useEffect(() => {
    if (token) cargarPaginas(token);
  }, [token]);

  function toggleModoOscuro() {
    const nuevo = !modoOscuro;
    setModoOscuro(nuevo);
    localStorage.setItem("modo_oscuro", String(nuevo));
  }

  async function cargarPaginas(t: string) {
    setCargandoPaginas(true);
    setError(null);
    try {
      const lista = await obtenerPaginas(t);
      setPaginas(lista);
    } catch (e: any) {
      setError(e.message);
      toast.error(e.message);
    } finally {
      setCargandoPaginas(false);
    }
  }

  function toggleSeleccion(id: string) {
    const nueva = new Set(seleccionadas);
    if (nueva.has(id)) nueva.delete(id);
    else nueva.add(id);
    setSeleccionadas(nueva);
  }

  function cerrarSesion() {
    fetch("/api/fb/auth/session", { method: "DELETE" }).catch(() => {});
    localStorage.removeItem("fb_token");
    setToken(null);
    setPaginas([]);
    setSeleccionadas(new Set());
    toast.success("Sesión cerrada");
  }

  // Facebook dijo que el token guardado ya no sirve: se descarta en silencio
  function descartarTokenInvalido() {
    localStorage.removeItem("fb_token");
    setToken(null);
    setPaginas([]);
    setSeleccionadas(new Set());
  }

  function limpiarHistorial() {
    if (confirm("¿Estás seguro de que quieres eliminar todo el historial?")) {
      setHistorial([]);
      localStorage.removeItem("historial_publicaciones");
      toast.success("Historial eliminado");
    }
  }

  function exportarCSV() {
    if (historial.length === 0) {
      toast.error("No hay historial para exportar");
      return;
    }
    const encabezado = ["Fecha", "Tipo", "Título", "Mensaje", "Páginas", "Éxitos", "Errores"];
    const filas = historial.map((p) => [
      p.fecha,
      p.tipo,
      `"${p.titulo.replace(/"/g, '""')}"`,
      `"${p.mensaje.replace(/"/g, '""')}"`,
      p.paginas,
      p.exitos,
      p.errores,
    ]);
    const csv = [encabezado, ...filas].map((f) => f.join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `reporte_publicaciones_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Reporte CSV descargado");
  }

  function abrirPreview() {
    if (seleccionadas.size === 0) {
      toast.error("Selecciona al menos una página.");
      return;
    }
    if (!archivo) {
      toast.error("Selecciona un archivo.");
      return;
    }
    setPreviewAbierto(true);
  }

  async function handlePublicar() {
    setPreviewAbierto(false);

    if (seleccionadas.size === 0 || !archivo) return;

    setPublicando(true);
    setResultados([]);
    setProgresoPorPagina({});
    const nuevosResultados: Resultado[] = [];
    const paginasAPublicar = paginas.filter((p) => seleccionadas.has(p.id));

    for (const pagina of paginasAPublicar) {
      const r = await publicarContenido(pagina, archivo, tipo, titulo, mensaje, (pct) => {
        setProgresoPorPagina((prev) => ({ ...prev, [pagina.id]: pct }));
      });
      nuevosResultados.push({ pagina: pagina.name, exito: r.success, mensaje: r.message });
      setResultados([...nuevosResultados]);

      if (r.success) {
        toast.success(`Publicado en ${pagina.name}`);
      } else {
        toast.error(`Error en ${pagina.name}: ${r.message}`);
      }
    }

    const publicacion: PublicacionHistorial = {
      id: Date.now().toString(),
      fecha: new Date().toLocaleString(),
      tipo: tipo,
      titulo: titulo || "Sin título",
      mensaje: mensaje || "Sin mensaje",
      paginas: nuevosResultados.length,
      exitos: nuevosResultados.filter((r) => r.exito).length,
      errores: nuevosResultados.filter((r) => !r.exito).length,
      resultados: nuevosResultados,
    };

    const nuevoHistorial = [publicacion, ...historial];
    setHistorial(nuevoHistorial);
    localStorage.setItem("historial_publicaciones", JSON.stringify(nuevoHistorial));

    setPublicando(false);
  }

  const nombresSeleccionados = paginas.filter((p) => seleccionadas.has(p.id)).map((p) => p.name);

  return (
    <AccesoGate token={token} onTokenInvalido={descartarTokenInvalido}>
    <div
      style={{
        minHeight: "100vh",
        background: theme.bg,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        transition: "background 0.2s",
      }}
    >
      {/* Navbar */}
      <nav
        style={{
          background: theme.cardBg,
          borderBottom: `1px solid ${theme.border}`,
          padding: "12px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "24px" }}>📱</span>
          <span style={{ fontWeight: "bold", fontSize: "18px", color: theme.text }}>
            Publicador Multi-Página
          </span>
          <span
            style={{
              background: theme.accentBg,
              color: theme.accent,
              fontSize: "10px",
              padding: "2px 8px",
              borderRadius: "12px",
              fontWeight: "600",
            }}
          >
            Pro
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button
            onClick={toggleModoOscuro}
            title="Cambiar tema"
            style={{
              background: "none",
              border: `1px solid ${theme.border}`,
              borderRadius: "6px",
              padding: "6px 10px",
              cursor: "pointer",
              fontSize: "14px",
            }}
          >
            {modoOscuro ? "☀️" : "🌙"}
          </button>
          {token && <span style={{ fontSize: "14px", color: "#34a853" }}>✅ Conectado</span>}
        </div>
      </nav>

      {/* Contenido */}
      <div className="app-wrap" style={{ display: "flex", alignItems: "flex-start", maxWidth: "1280px", margin: "0 auto" }}>
        {token && <Sidebar theme={theme} activo={tabActivo} onSelect={setTabActivo} onCerrarSesion={cerrarSesion} />}
        <div style={{ flex: 1, minWidth: 0, padding: "24px 16px" }}>
        <div
          style={{
            background: theme.cardBg,
            borderRadius: "8px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)",
            padding: "24px",
          }}
        >
          {(!token || tabActivo === "publicar") && <div style={{ marginBottom: "24px" }}>
            <h1 style={{ fontSize: "24px", fontWeight: "600", color: theme.text, margin: "0 0 4px 0" }}>
              Publica en Múltiples Páginas
            </h1>
            <p style={{ color: theme.subtext, fontSize: "14px", margin: "0" }}>
              Selecciona tus páginas y comparte contenido en todas simultáneamente
            </p>
          </div>}

          {error && (
            <div
              style={{
                background: "#fce8e6",
                color: "#c62828",
                padding: "12px 16px",
                borderRadius: "4px",
                marginBottom: "16px",
                fontSize: "14px",
              }}
            >
              ⚠️ {error}
            </div>
          )}

          {!token ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}>
              <div
                style={{
                  width: "80px",
                  height: "80px",
                  background: theme.accentBg,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 16px",
                }}
              >
                <span style={{ fontSize: "40px" }}>🔑</span>
              </div>
              <h2 style={{ fontSize: "20px", fontWeight: "500", color: theme.text }}>
                Conéctate con Facebook
              </h2>
              <p style={{ color: theme.subtext, marginBottom: "24px" }}>
                Autoriza la aplicación para empezar a publicar
              </p>
              <button
                  onClick={() => { window.location.href = getLoginUrl(); }}
                  style={{
                    background: "#1877f2",
                    color: "white",
                    border: "none",
                    padding: "12px 32px",
                    borderRadius: "6px",
                    fontSize: "16px",
                    fontWeight: "600",
                    cursor: "pointer",
                  }}
                >
                  Conectar con Facebook
                </button>
            </div>
          ) : (
            <>
              {tabActivo === "publicar" && (

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                  gap: "12px",
                  marginBottom: "24px",
                }}
              >
                <div style={{ background: "#e6f4ea", padding: "12px 16px", borderRadius: "6px" }}>
                  <div style={{ fontSize: "12px", color: "#1e7e34" }}>Estado</div>
                  <div style={{ fontSize: "18px", fontWeight: "600", color: "#1e7e34" }}>✅ Conectado</div>
                </div>
                <div style={{ background: theme.accentBg, padding: "12px 16px", borderRadius: "6px" }}>
                  <div style={{ fontSize: "12px", color: theme.accent }}>Páginas</div>
                  <div style={{ fontSize: "18px", fontWeight: "600", color: theme.accent }}>{paginas.length}</div>
                </div>
                <div style={{ background: "#f3e8fd", padding: "12px 16px", borderRadius: "6px" }}>
                  <div style={{ fontSize: "12px", color: "#7c3aed" }}>Seleccionadas</div>
                  <div style={{ fontSize: "18px", fontWeight: "600", color: "#7c3aed" }}>{seleccionadas.size}</div>
                </div>
                <button
                  onClick={cerrarSesion}
                  style={{
                    background: theme.formBg,
                    border: `1px solid ${theme.border}`,
                    padding: "12px 16px",
                    borderRadius: "6px",
                    fontSize: "14px",
                    color: theme.subtext,
                    cursor: "pointer",
                  }}
                >
                  🔒 Cerrar sesión
                </button>
              </div>
              )}

              {tabActivo === "inicio" ? (
                <Inicio theme={theme} onIr={setTabActivo} />
              ) : tabActivo === "tiktok" ? (
                <TikTok theme={theme} onIr={setTabActivo} />
              ) : tabActivo === "lote" ? (
                <Lote theme={theme} />
              ) : tabActivo === "cola" ? (
                <Cola theme={theme} />
              ) : tabActivo === "calendario" ? (
                <Calendario theme={theme} />
              ) : tabActivo === "metricas" ? (
                <Metricas theme={theme} />
              ) : tabActivo === "dashboard" ? (
                <Dashboard historial={historial} theme={theme} />
              ) : tabActivo === "eliminar" ? (
                <Eliminador theme={theme} />
              ) : tabActivo === "cuentas" ? (
                <CuentasManager tokenActual={token} theme={theme} />
              ) : tabActivo === "programadas" ? (
                <Programador theme={theme} />
              ) : tabActivo === "historial" ? (
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "16px",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    <h3 style={{ fontSize: "16px", fontWeight: "500", margin: "0", color: theme.text }}>
                      📜 Historial de publicaciones
                    </h3>
                    <div style={{ display: "flex", gap: "8px" }}>
                      {historial.length > 0 && (
                        <>
                          <button
                            onClick={exportarCSV}
                            style={{
                              background: theme.accentBg,
                              border: "none",
                              padding: "4px 12px",
                              borderRadius: "4px",
                              fontSize: "12px",
                              color: theme.accent,
                              cursor: "pointer",
                            }}
                          >
                            ⬇️ Exportar CSV
                          </button>
                          <button
                            onClick={limpiarHistorial}
                            style={{
                              background: "#fce8e6",
                              border: "none",
                              padding: "4px 12px",
                              borderRadius: "4px",
                              fontSize: "12px",
                              color: "#c62828",
                              cursor: "pointer",
                            }}
                          >
                            🗑️ Limpiar historial
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {historial.length === 0 ? (
                    <div style={{ textAlign: "center", padding: "40px 20px", color: theme.subtext }}>
                      <span style={{ fontSize: "48px", display: "block", marginBottom: "12px" }}>📭</span>
                      <p>No hay publicaciones en el historial</p>
                      <p style={{ fontSize: "13px" }}>Tus publicaciones aparecerán aquí después de publicar</p>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                      {historial.map((pub) => (
                        <div
                          key={pub.id}
                          style={{
                            border: `1px solid ${theme.border}`,
                            borderRadius: "6px",
                            padding: "16px",
                            background: theme.cardBg,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "flex-start",
                              flexWrap: "wrap",
                              gap: "8px",
                            }}
                          >
                            <div>
                              <div style={{ fontWeight: "600", color: theme.text }}>{pub.titulo}</div>
                              <div style={{ fontSize: "13px", color: theme.subtext }}>
                                {pub.fecha} • {pub.tipo} • {pub.paginas} páginas
                              </div>
                            </div>
                            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                              <span
                                style={{
                                  background: pub.exitos > 0 ? "#e6f4ea" : theme.formBg,
                                  color: "#1e7e34",
                                  padding: "2px 10px",
                                  borderRadius: "12px",
                                  fontSize: "12px",
                                }}
                              >
                                ✅ {pub.exitos}
                              </span>
                              {pub.errores > 0 && (
                                <span
                                  style={{
                                    background: "#fce8e6",
                                    color: "#c62828",
                                    padding: "2px 10px",
                                    borderRadius: "12px",
                                    fontSize: "12px",
                                  }}
                                >
                                  ❌ {pub.errores}
                                </span>
                              )}
                            </div>
                          </div>
                          {pub.mensaje && pub.mensaje !== "Sin mensaje" && (
                            <div
                              style={{
                                fontSize: "13px",
                                color: theme.text,
                                marginTop: "8px",
                                padding: "8px",
                                background: theme.formBg,
                                borderRadius: "4px",
                              }}
                            >
                              {pub.mensaje}
                            </div>
                          )}
                          {pub.resultados.length > 0 && (
                            <details style={{ marginTop: "8px" }}>
                              <summary style={{ fontSize: "13px", color: theme.accent, cursor: "pointer" }}>
                                Ver detalles por página
                              </summary>
                              <div
                                style={{
                                  marginTop: "8px",
                                  padding: "8px",
                                  background: theme.formBg,
                                  borderRadius: "4px",
                                  fontSize: "13px",
                                }}
                              >
                                {pub.resultados.map((r, i) => (
                                  <div
                                    key={i}
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      padding: "4px 0",
                                      borderBottom:
                                        i < pub.resultados.length - 1 ? `1px solid ${theme.border}` : "none",
                                      color: theme.text,
                                    }}
                                  >
                                    <span>{r.pagina}</span>
                                    <span style={{ color: r.exito ? "#1e7e34" : "#c62828" }}>
                                      {r.exito ? "✅" : "❌"} {r.mensaje}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </details>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {/* Páginas */}
                  <div style={{ marginBottom: "24px" }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "12px",
                      }}
                    >
                      <h3 style={{ fontSize: "16px", fontWeight: "500", color: theme.text }}>
                        📋 Páginas disponibles
                      </h3>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          onClick={() => setSeleccionadas(new Set(paginas.map((p) => p.id)))}
                          style={{
                            background: theme.accentBg,
                            border: "none",
                            padding: "4px 12px",
                            borderRadius: "4px",
                            fontSize: "12px",
                            color: theme.accent,
                            cursor: "pointer",
                          }}
                        >
                          Seleccionar todas
                        </button>
                        <button
                          onClick={() => setSeleccionadas(new Set())}
                          style={{
                            background: theme.formBg,
                            border: "none",
                            padding: "4px 12px",
                            borderRadius: "4px",
                            fontSize: "12px",
                            color: theme.subtext,
                            cursor: "pointer",
                          }}
                        >
                          Limpiar
                        </button>
                      </div>
                    </div>

                    {cargandoPaginas ? (
                      <div style={{ textAlign: "center", padding: "20px", color: theme.text }}>
                        Cargando páginas...
                      </div>
                    ) : (
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                          gap: "8px",
                        }}
                      >
                        {paginas.map((p) => (
                          <label
                            key={p.id}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              padding: "10px 12px",
                              background: seleccionadas.has(p.id) ? theme.accentBg : theme.cardBg,
                              border: seleccionadas.has(p.id) ? `1px solid ${theme.accent}` : `1px solid ${theme.border}`,
                              borderRadius: "6px",
                              cursor: "pointer",
                              transition: "all 0.2s",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={seleccionadas.has(p.id)}
                              onChange={() => toggleSeleccion(p.id)}
                              style={{ marginRight: "8px" }}
                            />
                            <span style={{ fontSize: "14px", color: theme.text }}>{p.name}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Formulario */}
                  <div
                    style={{
                      background: theme.formBg,
                      padding: "20px",
                      borderRadius: "6px",
                      border: `1px solid ${theme.border}`,
                    }}
                  >
                    <h3 style={{ fontSize: "16px", fontWeight: "500", margin: "0 0 16px 0", color: theme.text }}>
                      ✏️ Crear nueva publicación
                    </h3>

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
                            border: `1px solid ${theme.border}`,
                            borderRadius: "4px",
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
                      <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
                        Título
                      </label>
                      <input
                        type="text"
                        placeholder="Escribe un título..."
                        value={titulo}
                        onChange={(e) => setTitulo(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          border: `1px solid ${theme.border}`,
                          borderRadius: "4px",
                          fontSize: "14px",
                          background: theme.cardBg,
                          color: theme.text,
                        }}
                      />
                    </div>

                    <div style={{ marginBottom: "16px" }}>
                      <label style={{ fontSize: "13px", color: theme.subtext, display: "block", marginBottom: "4px" }}>
                        Mensaje
                      </label>
                      <textarea
                        placeholder="Escribe el mensaje..."
                        value={mensaje}
                        onChange={(e) => setMensaje(e.target.value)}
                        rows={3}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          border: `1px solid ${theme.border}`,
                          borderRadius: "4px",
                          fontSize: "14px",
                          resize: "vertical",
                          fontFamily: "inherit",
                          background: theme.cardBg,
                          color: theme.text,
                        }}
                      />
                    </div>

                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        onClick={abrirPreview}
                        disabled={publicando || seleccionadas.size === 0 || !archivo}
                        style={{
                          flex: 1,
                          padding: "12px",
                          background: "transparent",
                          border: `1px solid ${theme.accent}`,
                          color: theme.accent,
                          borderRadius: "6px",
                          fontSize: "15px",
                          fontWeight: "600",
                          cursor: publicando || seleccionadas.size === 0 || !archivo ? "not-allowed" : "pointer",
                          opacity: publicando || seleccionadas.size === 0 || !archivo ? 0.5 : 1,
                        }}
                      >
                        👁️ Vista previa
                      </button>
                      <button
                        onClick={abrirPreview}
                        disabled={publicando || seleccionadas.size === 0 || !archivo}
                        style={{
                          flex: 2,
                          padding: "12px",
                          background:
                            publicando || seleccionadas.size === 0 || !archivo ? "#dadce0" : theme.accent,
                          color: "white",
                          border: "none",
                          borderRadius: "6px",
                          fontSize: "16px",
                          fontWeight: "600",
                          cursor: publicando || seleccionadas.size === 0 || !archivo ? "not-allowed" : "pointer",
                        }}
                      >
                        {publicando
                          ? "Publicando..."
                          : `🚀 Publicar en ${seleccionadas.size} página${seleccionadas.size > 1 ? "s" : ""}`}
                      </button>
                    </div>
                  </div>

                  {/* Progreso en curso */}
                  {publicando && (
                    <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "8px" }}>
                      {paginas
                        .filter((p) => seleccionadas.has(p.id))
                        .map((p) => {
                          const pct = progresoPorPagina[p.id] ?? 0;
                          return (
                            <div key={p.id}>
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  fontSize: "12px",
                                  color: theme.subtext,
                                  marginBottom: "2px",
                                }}
                              >
                                <span>{p.name}</span>
                                <span>{pct}%</span>
                              </div>
                              <div style={{ background: theme.formBg, borderRadius: "4px", height: "6px", overflow: "hidden" }}>
                                <div
                                  style={{
                                    width: `${pct}%`,
                                    height: "100%",
                                    background: theme.accent,
                                    transition: "width 0.2s",
                                  }}
                                />
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  )}

                  {/* Resultados */}
                  {resultados.length > 0 && !publicando && (
                    <div style={{ marginTop: "24px" }}>
                      <h3 style={{ fontSize: "16px", fontWeight: "500", margin: "0 0 12px 0", color: theme.text }}>
                        📊 Resultados
                      </h3>
                      <div style={{ overflow: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
                          <thead>
                            <tr style={{ background: theme.formBg, borderBottom: `2px solid ${theme.border}` }}>
                              <th style={{ padding: "10px", textAlign: "left", color: theme.text }}>Página</th>
                              <th style={{ padding: "10px", textAlign: "left", color: theme.text }}>Estado</th>
                              <th style={{ padding: "10px", textAlign: "left", color: theme.text }}>Mensaje</th>
                            </tr>
                          </thead>
                          <tbody>
                            {resultados.map((r, i) => (
                              <tr key={i} style={{ borderBottom: `1px solid ${theme.border}` }}>
                                <td style={{ padding: "10px", color: theme.text }}>{r.pagina}</td>
                                <td style={{ padding: "10px" }}>
                                  <span
                                    style={{
                                      background: r.exito ? "#e6f4ea" : "#fce8e6",
                                      color: r.exito ? "#1e7e34" : "#c62828",
                                      padding: "2px 12px",
                                      borderRadius: "12px",
                                      fontSize: "12px",
                                    }}
                                  >
                                    {r.exito ? "✅ Éxito" : "❌ Error"}
                                  </span>
                                </td>
                                <td style={{ padding: "10px", color: theme.text }}>{r.mensaje}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
        </div>
      </div>

      <PreviewModal
        abierto={previewAbierto}
        onClose={() => setPreviewAbierto(false)}
        onConfirmar={handlePublicar}
        titulo={titulo}
        mensaje={mensaje}
        archivo={archivo}
        tipo={tipo}
        paginasSeleccionadas={nombresSeleccionados}
        theme={theme}
      />
    </div>
    </AccesoGate>
  );
}

