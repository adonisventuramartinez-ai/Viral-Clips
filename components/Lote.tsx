"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { supabaseBrowser, BUCKET } from "@/lib/supabaseClient";
import { TipoContenido, validarArchivo } from "@/lib/facebook";
import { aplicarPlantilla, parsearHoras, repartirFechas } from "@/lib/lote";

interface Theme {
  cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string; accentText?: string;
}
interface Cuenta { id: number; nombre: string }
interface PaginaCuenta { id: string; name: string }
interface Elemento { nombre: string; file?: File; path?: string; descripcion?: string; autor?: string; importacionId?: number }
interface Importado { id: number; titulo: string | null; descripcion: string | null; autor: string | null; duracion: number | null; archivo_url: string }
interface Plantilla { id: number; nombre: string; titulo: string | null; mensaje: string | null }

const DIAS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

function aInputLocal(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function Lote({ theme }: { theme: Theme }) {
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [cuentaId, setCuentaId] = useState<number | null>(null);
  const [paginas, setPaginas] = useState<PaginaCuenta[]>([]);
  const [sel, setSel] = useState<Set<string>>(new Set());

  const [tipo, setTipo] = useState<TipoContenido>("reel");
  const [archivos, setArchivos] = useState<Elemento[]>([]);
  const [importados, setImportados] = useState<Importado[]>([]);
  const [selImp, setSelImp] = useState<Set<number>>(new Set());
  const [titulo, setTitulo] = useState("");
  const [mensaje, setMensaje] = useState("");

  const [plantillas, setPlantillas] = useState<Plantilla[]>([]);
  const [inicio, setInicio] = useState(() => aInputLocal(new Date(Date.now() + 3600_000)));
  const [horasTxt, setHorasTxt] = useState("09:00, 18:00");
  const [dias, setDias] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);
  const [variacion, setVariacion] = useState(10);
  const [semilla, setSemilla] = useState(1);

  const [enviando, setEnviando] = useState(false);
  const [progreso, setProgreso] = useState("");
  const entrada = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("/api/fb/accounts").then((r) => r.json()).then((d) => setCuentas(d.cuentas || []));
    cargarPlantillas();
    cargarImportados();
  }, []);

  useEffect(() => {
    setSel(new Set());
    if (!cuentaId) return setPaginas([]);
    fetch(`/api/fb/accounts/${cuentaId}/paginas`)
      .then((r) => r.json())
      .then((d) => (d.error ? (toast.error(d.error), setPaginas([])) : setPaginas(d.paginas || [])));
  }, [cuentaId]);

  function cargarImportados() {
    fetch("/api/fb/importar").then((r) => r.json()).then((d) =>
      setImportados((d.importaciones || []).filter((i: any) => i.tipo === "video" && i.estado === "listo" && i.archivo_url))
    ).catch(() => {});
  }

  function agregarImportados() {
    const nuevos: Elemento[] = importados
      .filter((i) => selImp.has(i.id))
      .map((i) => ({
        nombre: (i.titulo || `TikTok ${i.id}`).slice(0, 80),
        path: i.archivo_url, descripcion: i.descripcion || "", autor: i.autor || "", importacionId: i.id,
      }));
    setArchivos((a) => [...a, ...nuevos].slice(0, 60));
    setSelImp(new Set());
  }

  function cargarPlantillas() {
    fetch("/api/fb/plantillas").then((r) => r.json()).then((d) => setPlantillas(d.plantillas || []));
  }

  const horas = useMemo(() => parsearHoras(horasTxt), [horasTxt]);
  const fechas = useMemo(
    () => repartirFechas(archivos.length, { inicio: new Date(inicio), horas, dias, variacionMin: variacion, semilla }),
    [archivos.length, inicio, horas, dias, variacion, semilla]
  );
  const sinHueco = archivos.length > 0 && fechas.length < archivos.length;

  function agregar(lista: FileList | null) {
    if (!lista) return;
    const nuevos: Elemento[] = [];
    for (const f of Array.from(lista)) {
      const v = validarArchivo(f, tipo);
      if (!v.valido) toast.error(`${f.name}: ${v.error}`);
      else nuevos.push({ nombre: f.name, file: f });
    }
    setArchivos((a) => [...a, ...nuevos].slice(0, 60));
    if (entrada.current) entrada.current.value = "";
  }

  function mover(i: number, delta: number) {
    setArchivos((a) => {
      const j = i + delta;
      if (j < 0 || j >= a.length) return a;
      const c = [...a];
      [c[i], c[j]] = [c[j], c[i]];
      return c;
    });
  }

  async function guardarPlantilla() {
    const nombre = prompt("Nombre de la plantilla:");
    if (!nombre) return;
    const res = await fetch("/api/fb/plantillas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre, titulo, mensaje }),
    });
    const d = await res.json();
    if (d.error) return toast.error(d.error);
    toast.success("Plantilla guardada");
    cargarPlantillas();
  }

  async function borrarPlantilla(id: number) {
    await fetch(`/api/fb/plantillas?id=${id}`, { method: "DELETE" });
    cargarPlantillas();
  }

  async function programarLote() {
    if (!cuentaId) return toast.error("Selecciona una cuenta");
    if (!sel.size) return toast.error("Selecciona al menos una página");
    if (!archivos.length) return toast.error("Agrega archivos");
    if (sinHueco || fechas.length === 0) return toast.error("Revisa los horarios: no alcanzan para todos los archivos");

    setEnviando(true);
    try {
      const resultado: any[] = new Array(archivos.length).fill(null);
      const fallidos: string[] = [];
      let hechos = 0;

      const subirUno = async (i: number) => {
        const f = archivos[i];
        try {
          let ruta = f.path || "";
          if (f.file) {
            const prep = await (await fetch("/api/fb/subir-archivo", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ nombreArchivo: f.file.name }),
            })).json();
            if (prep.error) throw new Error(prep.error);
            const { error } = await supabaseBrowser.storage.from(BUCKET).uploadToSignedUrl(prep.path, prep.token, f.file);
            if (error) throw error;
            ruta = prep.path;
          }
          resultado[i] = {
            archivo_url: ruta,
            archivo_nombre: f.nombre,
            titulo: aplicarPlantilla(titulo, i + 1, f.nombre, f.descripcion || "", f.autor || ""),
            mensaje: aplicarPlantilla(mensaje, i + 1, f.nombre, f.descripcion || "", f.autor || ""),
            fecha_programada: fechas[i].toISOString(),
            importacion_id: f.importacionId,
          };
        } catch (e: any) {
          fallidos.push(`${f.nombre} (${e.message || "error"})`);
        } finally {
          hechos++;
          setProgreso(`Subiendo ${hechos} de ${archivos.length}…`);
        }
      };

      // 3 subidas a la vez: un lote de 40 videos tarda ~3 veces menos que subiéndolos de uno en uno
      setProgreso(`Subiendo 0 de ${archivos.length}…`);
      let siguiente = 0;
      await Promise.all(
        Array.from({ length: Math.min(3, archivos.length) }, async () => {
          while (siguiente < archivos.length) await subirUno(siguiente++);
        })
      );
      const items = resultado.filter(Boolean);
      if (!items.length) throw new Error("No se pudo subir ningún archivo");

      setProgreso("Programando…");
      const res = await (await fetch("/api/fb/schedule/lote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cuenta_id: cuentaId,
          paginas: paginas.filter((p) => sel.has(p.id)).map((p) => ({ id: p.id, name: p.name })),
          tipo,
          items,
        }),
      })).json();
      if (res.error) throw new Error(res.error);

      toast.success(`${res.creados} publicaciones programadas`);
      if (fallidos.length) toast.error(`No se subieron: ${fallidos.join(", ")}`, { duration: 8000 });
      setArchivos([]);
      cargarImportados();
    } catch (e: any) {
      toast.error(e.message || "Error al programar el lote");
    } finally {
      setEnviando(false);
      setProgreso("");
    }
  }

  const caja = { background: theme.formBg, border: `1px solid ${theme.border}`, borderRadius: 8, padding: 16, marginBottom: 16 } as const;
  const campo = { width: "100%", padding: 8, borderRadius: 6, border: `1px solid ${theme.border}`, background: theme.cardBg, color: theme.text, boxSizing: "border-box" } as const;
  const etiqueta = { display: "block", fontSize: 13, color: theme.subtext, marginBottom: 6 } as const;

  return (
    <div style={{ color: theme.text }}>
      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 16px" }}>📦 Programación en lote</h3>

      <div style={caja}>
        <label style={etiqueta}>1. Cuenta y páginas</label>
        <select style={campo} value={cuentaId ?? ""} onChange={(e) => setCuentaId(e.target.value ? Number(e.target.value) : null)}>
          <option value="">— Elige una cuenta —</option>
          {cuentas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
          {paginas.map((p) => (
            <label key={p.id} style={{ fontSize: 13, display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={sel.has(p.id)} onChange={() => {
                const n = new Set(sel); n.has(p.id) ? n.delete(p.id) : n.add(p.id); setSel(n);
              }} />
              {p.name}
            </label>
          ))}
        </div>
      </div>

      <div style={caja}>
        <label style={etiqueta}>2. Tipo y archivos (hasta 60)</label>
        <select style={{ ...campo, width: "auto", marginBottom: 10 }} value={tipo} onChange={(e) => { setTipo(e.target.value as TipoContenido); setArchivos([]); }}>
          <option value="reel">Reels</option>
          <option value="video">Videos</option>
          <option value="foto">Fotos</option>
        </select>
        <div>
          <input ref={entrada} type="file" multiple accept={tipo === "foto" ? "image/*" : "video/*"} onChange={(e) => agregar(e.target.files)} />
        </div>
        {archivos.map((f, i) => (
          <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, padding: "6px 0", borderTop: `1px solid ${theme.border}`, marginTop: i === 0 ? 10 : 0 }}>
            <span style={{ width: 24, color: theme.subtext }}>{i + 1}</span>
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.nombre}</span>
            <span style={{ color: fechas[i] ? theme.accent : "#c0392b", whiteSpace: "nowrap" }}>
              {fechas[i] ? fechas[i].toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "sin horario"}
            </span>
            <button onClick={() => mover(i, -1)} disabled={i === 0}>↑</button>
            <button onClick={() => mover(i, 1)} disabled={i === archivos.length - 1}>↓</button>
            <button onClick={() => setArchivos((a) => a.filter((_, k) => k !== i))}>✕</button>
          </div>
        ))}
      </div>

      {tipo !== "foto" && (() => {
        const enLote = new Set(archivos.map((a) => a.importacionId));
        const disp = importados.filter((i) => !enLote.has(i.id));
        if (!disp.length) return null;
        return (
          <div style={caja}>
            <label style={etiqueta}>🎵 Importados de TikTok / Instagram ({disp.length} listos)</label>
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <button onClick={() => setSelImp(new Set(disp.map((i) => i.id)))}>Marcar todos</button>
              <button onClick={() => setSelImp(new Set())}>Ninguno</button>
              <button onClick={agregarImportados} disabled={!selImp.size}>Agregar {selImp.size} al lote</button>
            </div>
            {disp.map((i) => (
              <label key={i.id} style={{ display: "flex", gap: 8, fontSize: 13, padding: "4px 0", borderTop: `1px solid ${theme.border}` }}>
                <input type="checkbox" checked={selImp.has(i.id)} onChange={() => {
                  const n = new Set(selImp); n.has(i.id) ? n.delete(i.id) : n.add(i.id); setSelImp(n);
                }} />
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{i.titulo || `TikTok ${i.id}`}</span>
                <span style={{ color: tipo === "reel" && (i.duracion || 0) > 90 ? "#f59e0b" : theme.subtext }}>
                  {i.duracion ? `${i.duracion}s` : ""}{tipo === "reel" && (i.duracion || 0) > 90 ? " ⚠️ >90 s" : ""}
                </span>
              </label>
            ))}
          </div>
        );
      })()}

      <div style={caja}>
        <label style={etiqueta}>3. Texto (variables: {"{n}"} = número, {"{nombre}"} = nombre del archivo)</label>
        <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <select style={{ ...campo, width: "auto" }} value="" onChange={(e) => {
            const p = plantillas.find((x) => x.id === Number(e.target.value));
            if (p) { setTitulo(p.titulo || ""); setMensaje(p.mensaje || ""); }
          }}>
            <option value="">Cargar plantilla…</option>
            {plantillas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
          <button onClick={guardarPlantilla}>💾 Guardar como plantilla</button>
        </div>
        {plantillas.length > 0 && (
          <div style={{ fontSize: 12, color: theme.subtext, marginBottom: 8 }}>
            {plantillas.map((p) => (
              <span key={p.id} style={{ marginRight: 10 }}>{p.nombre} <a style={{ cursor: "pointer" }} onClick={() => borrarPlantilla(p.id)}>🗑</a></span>
            ))}
          </div>
        )}
        <input style={{ ...campo, marginBottom: 8 }} placeholder="Título (opcional)" value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        <textarea style={{ ...campo, minHeight: 90 }} placeholder="Descripción / hashtags" value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
      </div>

      <div style={caja}>
        <label style={etiqueta}>4. Cuándo publicar</label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          <div>
            <label style={etiqueta}>Empezar desde</label>
            <input type="datetime-local" style={campo} value={inicio} onChange={(e) => setInicio(e.target.value)} />
          </div>
          <div>
            <label style={etiqueta}>Horas del día (separadas por coma)</label>
            <input style={campo} value={horasTxt} onChange={(e) => setHorasTxt(e.target.value)} placeholder="09:00, 13:00, 20:00" />
          </div>
          <div>
            <label style={etiqueta}>Variación ± minutos</label>
            <input type="number" min={0} max={30} style={campo} value={variacion} onChange={(e) => setVariacion(Number(e.target.value) || 0)} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
          {DIAS.map((d, i) => (
            <label key={d} style={{ fontSize: 13 }}>
              <input type="checkbox" checked={dias.includes(i)} onChange={() => setDias((x) => (x.includes(i) ? x.filter((k) => k !== i) : [...x, i]))} /> {d}
            </label>
          ))}
          <button onClick={() => setSemilla((s) => s + 1)}>🎲 Mezclar minutos</button>
        </div>
        {sinHueco && <p style={{ color: "#c0392b", fontSize: 13 }}>Los horarios solo alcanzan para {fechas.length} de {archivos.length} archivos.</p>}
      </div>

      <button
        onClick={programarLote}
        disabled={enviando}
        style={{ padding: "12px 20px", background: theme.accent, color: theme.accentText || "#fff", border: "none", borderRadius: 8, fontWeight: 600, cursor: enviando ? "wait" : "pointer" }}
      >
        {enviando ? progreso || "Trabajando…" : `Programar ${archivos.length || ""} publicaciones`}
      </button>
    </div>
  );
}

