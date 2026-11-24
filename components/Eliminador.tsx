"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import {
  FILTRO_VACIO, Filtro, ItemFb, TIPOS, TipoContenido, aCsv, confirmacionCorrecta, confirmacionEsperada, filtrar, trocear,
} from "@/lib/eliminador";

interface Theme { cardBg: string; formBg: string; border: string; text: string; subtext: string; accent: string; accentBg: string; accentText?: string }
interface Cuenta { id: number; nombre: string }
interface Pagina { id: string; name: string }
type Fase = "elegir" | "confirmar" | "borrando" | "fin";

const LOTE = 10;
const MAX_CARGA = 3000;
const ROJO = "#ef4444";
const dormir = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Eliminador({ theme }: { theme: Theme }) {
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [cuentaId, setCuentaId] = useState<number | null>(null);
  const [paginas, setPaginas] = useState<Pagina[]>([]);
  const [paginaId, setPaginaId] = useState("");
  const [tipo, setTipo] = useState<TipoContenido>("reels");

  const [items, setItems] = useState<ItemFb[]>([]);
  const [cargando, setCargando] = useState(false);
  const [completo, setCompleto] = useState(false);
  const [filtro, setFiltro] = useState<Filtro>(FILTRO_VACIO);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [mostrar, setMostrar] = useState(120);

  const [fase, setFase] = useState<Fase>("elegir");
  const [escrito, setEscrito] = useState("");
  const [entiendo, setEntiendo] = useState(false);
  const [aBorrar, setAborrar] = useState<ItemFb[]>([]);
  const [hechos, setHechos] = useState(0);
  const [fallos, setFallos] = useState<{ item: ItemFb; error: string }[]>([]);
  const [aviso, setAviso] = useState("");
  const parar = useRef(false);
  const cancelarCarga = useRef(false);
  const cursorRef = useRef<string | undefined>(undefined);

  const nombrePagina = paginas.find((p) => p.id === paginaId)?.name || "";

  useEffect(() => {
    fetch("/api/fb/accounts").then((r) => r.json()).then((d) => {
      const c: Cuenta[] = d.cuentas || [];
      setCuentas(c);
      if (c.length) setCuentaId(c[0].id);
    }).catch(() => toast.error("No se pudieron cargar las cuentas"));
  }, []);

  useEffect(() => {
    setPaginas([]); setPaginaId(""); reiniciar();
    if (!cuentaId) return;
    fetch(`/api/accounts/${cuentaId}/paginas`).then((r) => r.json()).then((d) => {
      if (d.error) return toast.error(d.error);
      setPaginas(d.paginas || []);
      if (d.paginas?.length) setPaginaId(d.paginas[0].id);
    }).catch(() => toast.error("No se pudieron cargar las páginas"));
  }, [cuentaId]);

  useEffect(() => { reiniciar(); }, [paginaId, tipo]);

  function reiniciar() {
    cancelarCarga.current = true;
    cursorRef.current = undefined;
    setItems([]); setSel(new Set()); setCompleto(false); setFase("elegir"); setFallos([]); setAviso(""); setMostrar(120);
  }

  // Espera con cuenta atrás visible. Devuelve false si se canceló durante la espera.
  async function esperar(seg: number, cancelar: { current: boolean }, motivo: string) {
    for (let t = seg; t > 0 && !cancelar.current; t--) { setAviso(`${motivo} Sigo en ${t} s…`); await dormir(1000); }
    setAviso("");
    return !cancelar.current;
  }

  // Carga páginas de contenido hasta `hasta` elementos (o hasta que se acabe). Se puede detener.
  async function cargar(hasta: number) {
    if (!cuentaId || !paginaId || cargando) return;
    setCargando(true);
    cancelarCarga.current = false;
    let acumulado = [...items];
    let cursor = cursorRef.current;
    let pausas = 0;
    try {
      while (!cancelarCarga.current && acumulado.length < hasta) {
        const q = new URLSearchParams({ cuenta: String(cuentaId), pagina: paginaId, tipo, ...(cursor ? { despues: cursor } : {}) });
        const r = await fetch(`/api/eliminar?${q}`);
        const d = await r.json().catch(() => ({}));
        if (!r.ok) {
          if (d.pausa) {
            if (++pausas > 3) throw new Error("Meta sigue limitando tu app (error #4). Espera ~1 hora y continúa; lo ya cargado se conserva.");
            if (!(await esperar(60 * pausas, cancelarCarga, "Facebook limitó el ritmo (límite de la app)."))) break;
            continue;
          }
          throw new Error(d.error || "No se pudo leer el contenido");
        }
        const vistos = new Set(acumulado.map((i) => i.id));
        acumulado = [...acumulado, ...(d.items as ItemFb[]).filter((i) => !vistos.has(i.id))];
        cursor = d.siguiente || undefined;
        cursorRef.current = cursor;
        setItems(acumulado);
        if (!cursor) { setCompleto(true); break; }
      }
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setItems(acumulado);
      setCargando(false);
    }
  }

  const visibles = useMemo(() => filtrar(items, filtro), [items, filtro]);
  const seleccionados = useMemo(() => items.filter((i) => sel.has(i.id)), [items, sel]);

  const alternar = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const marcarVisibles = () => setSel((s) => new Set([...s, ...visibles.map((v) => v.id)]));
  const soloVisibles = () => setSel(new Set(visibles.map((v) => v.id)));
  const limpiar = () => setSel(new Set());

  function respaldo(lista: ItemFb[]) {
    const blob = new Blob(["\ufeff" + aCsv(lista)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `respaldo-${(nombrePagina || "pagina").replace(/\W+/g, "_")}-${tipo}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function irAConfirmar() {
    setAborrar(seleccionados); setEscrito(""); setEntiendo(false); setFase("confirmar");
  }

  async function ejecutar(lista: ItemFb[]) {
    setAborrar(lista); setFase("borrando"); setHechos(0); setFallos([]); parar.current = false;
    const porId = new Map(lista.map((i) => [i.id, i]));
    const fallosAcum: { item: ItemFb; error: string }[] = [];
    let ok = 0;
    let pausas = 0;
    const borrados = new Set<string>();

    for (const trozo of trocear(lista.map((i) => i.id), LOTE)) {
      let pendiente = trozo;
      let intentos = 0;
      while (pendiente.length && !parar.current) {
        let d: any;
        try {
          const r = await fetch("/api/fb/eliminar", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cuenta: cuentaId, pagina: paginaId, ids: pendiente }),
          });
          d = await r.json().catch(() => ({}));
          if (!r.ok && !d.resultados) throw new Error(d.error || `Error ${r.status}`);
        } catch (e: any) {
          if (++intentos > 3) { pendiente.forEach((id) => fallosAcum.push({ item: porId.get(id)!, error: e.message })); pendiente = []; break; }
          await dormir(3000 * intentos);
          continue;
        }
        for (const x of d.resultados || []) {
          if (x.ok) { ok++; borrados.add(x.id); } else fallosAcum.push({ item: porId.get(x.id)!, error: x.error || "Error" });
        }
        setHechos(ok); setFallos([...fallosAcum]);
        pendiente = d.sinProcesar || [];
        if (d.fatal) { parar.current = true; toast.error("Facebook rechazó el permiso o el token. Reconecta la cuenta y reintenta."); break; }
        if (d.pausa && pendiente.length) {
          if (++pausas > 4) {
            parar.current = true;
            toast.error("Meta limitó tu app (error #4). Espera ~1 hora y pulsa «Reintentar los que faltan».");
            break;
          }
          await esperar(Math.min(300, 60 * pausas), parar, "Facebook limitó el ritmo (límite de la app).");
        }
      }
      if (parar.current) break;
    }
    setItems((prev) => prev.filter((i) => !borrados.has(i.id)));
    setSel((s) => new Set([...s].filter((id) => !borrados.has(id))));
    setAviso(""); setFase("fin");
    if (ok) toast.success(`${ok} eliminados`);
  }

  // ---- estilos
  const caja: React.CSSProperties = { background: theme.cardBg, border: `1px solid ${theme.border}`, borderRadius: 12, padding: 16, marginBottom: 14 };
  const campo: React.CSSProperties = { background: theme.formBg, color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 14 };
  const btn = (primario = false, peligro = false): React.CSSProperties => ({
    padding: "8px 14px", borderRadius: 8, fontSize: 13, cursor: "pointer", fontWeight: 600,
    border: `1px solid ${peligro ? ROJO : primario ? theme.accent : theme.border}`,
    background: peligro ? ROJO : primario ? theme.accent : "transparent",
    color: peligro ? "#fff" : primario ? theme.accentText || "#fff" : theme.text,
  });
  const total = aBorrar.length;
  const pct = total ? Math.round(((hechos + fallos.length) / total) * 100) : 0;

  return (
    <div style={{ color: theme.text }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 20 }}>🗑️ Eliminador masivo</h2>
      <p style={{ margin: "0 0 14px", fontSize: 13, color: theme.subtext }}>
        Borra reels, videos, fotos o publicaciones de tus páginas en bloque. <b style={{ color: ROJO }}>Lo borrado no se puede recuperar.</b>
      </p>

      {fase === "elegir" && (
        <>
          <div style={{ ...caja, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <select value={cuentaId ?? ""} onChange={(e) => setCuentaId(Number(e.target.value))} style={campo}>
              {cuentas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
            <select value={paginaId} onChange={(e) => setPaginaId(e.target.value)} style={campo}>
              {paginas.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {TIPOS.map((t) => (
                <button key={t.id} title={t.ayuda} onClick={() => setTipo(t.id)}
                  style={{ ...btn(tipo === t.id), padding: "7px 12px" }}>{t.icono} {t.texto}</button>
              ))}
            </div>
          </div>

          {!cuentas.length && <div style={caja}>Aún no tienes cuentas conectadas. Ve a la pestaña <b>Cuentas</b>.</div>}

          {paginaId && (
            <div style={{ ...caja, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <button style={btn(true)} disabled={cargando} onClick={() => cargar(items.length + 100)}>
                {items.length ? "Cargar 100 más" : "Cargar contenido"}
              </button>
              <button style={btn()} disabled={cargando || completo} onClick={() => cargar(MAX_CARGA)}>Cargar todo (hasta {MAX_CARGA})</button>
              {cargando && <button style={btn(false, true)} onClick={() => { cancelarCarga.current = true; }}>Detener</button>}
              <span style={{ fontSize: 13, color: theme.subtext }}>
                {cargando ? "Leyendo… " : ""}{items.length} cargados{completo ? " (es todo lo que hay)" : ""}
              </span>
              {aviso && <span style={{ fontSize: 13, color: "#f59e0b" }}>{aviso}</span>}
            </div>
          )}

          {items.length > 0 && (
            <>
              <div style={{ ...caja, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <input placeholder="🔎 Texto contiene…" value={filtro.texto} onChange={(e) => setFiltro({ ...filtro, texto: e.target.value })} style={{ ...campo, minWidth: 180 }} />
                <label style={{ fontSize: 12, color: theme.subtext }}>Desde <input type="date" value={filtro.desde} onChange={(e) => setFiltro({ ...filtro, desde: e.target.value })} style={campo} /></label>
                <label style={{ fontSize: 12, color: theme.subtext }}>Hasta <input type="date" value={filtro.hasta} onChange={(e) => setFiltro({ ...filtro, hasta: e.target.value })} style={campo} /></label>
                <select value={filtro.masDeDias ?? ""} onChange={(e) => setFiltro({ ...filtro, masDeDias: e.target.value ? Number(e.target.value) : null })} style={campo}>
                  <option value="">Cualquier antigüedad</option>
                  <option value="30">Más de 30 días</option>
                  <option value="90">Más de 90 días</option>
                  <option value="180">Más de 6 meses</option>
                  <option value="365">Más de 1 año</option>
                </select>
                <button style={btn()} onClick={() => setFiltro(FILTRO_VACIO)}>Quitar filtros</button>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10, position: "sticky", top: 0, background: theme.cardBg, padding: "8px 0", zIndex: 5 }}>
                <span style={{ fontSize: 13 }}><b>{visibles.length}</b> coinciden · <b style={{ color: seleccionados.length ? ROJO : theme.subtext }}>{seleccionados.length}</b> marcados</span>
                <button style={btn()} onClick={marcarVisibles}>☑ Marcar los {visibles.length} filtrados</button>
                <button style={btn()} onClick={soloVisibles}>Solo los filtrados</button>
                <button style={btn()} onClick={limpiar}>Desmarcar todo</button>
                <button style={btn()} disabled={!seleccionados.length} onClick={() => respaldo(seleccionados)}>⬇ Respaldo CSV</button>
                <button style={{ ...btn(false, true), opacity: seleccionados.length ? 1 : 0.4 }} disabled={!seleccionados.length} onClick={irAConfirmar}>
                  🗑️ Eliminar {seleccionados.length}
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(230px,1fr))", gap: 10 }}>
                {visibles.slice(0, mostrar).map((it) => {
                  const on = sel.has(it.id);
                  return (
                    <div key={it.id} onClick={() => alternar(it.id)} style={{
                      display: "flex", gap: 10, padding: 8, borderRadius: 10, cursor: "pointer",
                      border: `2px solid ${on ? ROJO : theme.border}`, background: on ? "rgba(239,68,68,.08)" : theme.cardBg,
                    }}>
                      <div style={{ width: 64, height: 64, borderRadius: 8, background: theme.formBg, flexShrink: 0, overflow: "hidden" }}>
                        {it.miniatura && <img src={it.miniatura} alt="" loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
                      </div>
                      <div style={{ minWidth: 0, fontSize: 12 }}>
                        <div style={{ color: theme.subtext }}>{it.fecha ? new Date(it.fecha).toLocaleDateString() : "—"}{it.duracion ? ` · ${it.duracion}s` : ""}</div>
                        <div style={{ overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{it.texto || <i style={{ color: theme.subtext }}>(sin texto)</i>}</div>
                        {it.enlace && <a href={it.enlace} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} style={{ color: theme.accent }}>ver</a>}
                      </div>
                    </div>
                  );
                })}
              </div>
              {visibles.length > mostrar && (
                <div style={{ textAlign: "center", margin: 14 }}>
                  <button style={btn()} onClick={() => setMostrar(mostrar + 240)}>Mostrar más ({visibles.length - mostrar} ocultos; los filtros y "marcar" los incluyen)</button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {fase === "confirmar" && (
        <div style={{ ...caja, borderColor: ROJO }}>
          <h3 style={{ margin: "0 0 8px", color: ROJO }}>⚠️ Vas a eliminar {total} {TIPOS.find((t) => t.id === tipo)?.texto.toLowerCase()} de «{nombrePagina}»</h3>
          <p style={{ fontSize: 13, color: theme.subtext }}>
            Es permanente: Facebook no los restaura. Te recomiendo bajar el respaldo CSV (guarda ID, fecha, texto y enlace; <b>no</b> guarda el video o la foto).
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            <button style={btn()} onClick={() => respaldo(aBorrar)}>⬇ Descargar respaldo CSV</button>
          </div>
          <label style={{ display: "flex", gap: 8, fontSize: 13, marginBottom: 10 }}>
            <input type="checkbox" checked={entiendo} onChange={(e) => setEntiendo(e.target.checked)} />
            Entiendo que no se puede deshacer.
          </label>
          <div style={{ fontSize: 13, marginBottom: 6 }}>Para confirmar escribe <b>{confirmacionEsperada(total)}</b>:</div>
          <input value={escrito} onChange={(e) => setEscrito(e.target.value)} style={{ ...campo, width: 240 }} autoFocus />
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button style={btn()} onClick={() => setFase("elegir")}>← Volver</button>
            <button style={{ ...btn(false, true), opacity: entiendo && confirmacionCorrecta(escrito, total) ? 1 : 0.4 }}
              disabled={!(entiendo && confirmacionCorrecta(escrito, total))} onClick={() => ejecutar(aBorrar)}>
              🗑️ Eliminar {total} definitivamente
            </button>
          </div>
        </div>
      )}

      {(fase === "borrando" || fase === "fin") && (
        <div style={caja}>
          <h3 style={{ margin: "0 0 10px" }}>{fase === "borrando" ? "Eliminando…" : parar.current ? "Detenido" : "Terminado"}</h3>
          <div style={{ height: 12, background: theme.formBg, borderRadius: 6, overflow: "hidden", border: `1px solid ${theme.border}` }}>
            <div style={{ width: `${pct}%`, height: "100%", background: fallos.length ? "#f59e0b" : theme.accent, transition: "width .3s" }} />
          </div>
          <div style={{ fontSize: 13, margin: "8px 0" }}>
            ✅ {hechos} eliminados · ❌ {fallos.length} con error · {total - hechos - fallos.length} pendientes · {pct}%
          </div>
          {aviso && <div style={{ fontSize: 13, color: "#f59e0b", marginBottom: 8 }}>{aviso}</div>}
          {fase === "borrando" && <button style={btn(false, true)} onClick={() => { parar.current = true; }}>⏹ Detener</button>}
          {fase === "fin" && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {(fallos.length > 0 || hechos + fallos.length < total) && (
                <button style={btn(true)} onClick={() => ejecutar(aBorrar.filter((i) => items.some((x) => x.id === i.id)))}>
                  🔁 Reintentar los que faltan
                </button>
              )}
              <button style={btn()} onClick={() => { setFase("elegir"); setFallos([]); }}>Volver a la lista</button>
            </div>
          )}
          {fallos.length > 0 && (
            <details style={{ marginTop: 10, fontSize: 12 }}>
              <summary style={{ cursor: "pointer", color: "#f59e0b" }}>Ver errores ({fallos.length})</summary>
              <div style={{ maxHeight: 220, overflow: "auto", marginTop: 6 }}>
                {fallos.slice(0, 200).map((f, i) => (
                  <div key={i} style={{ padding: "4px 0", borderBottom: `1px solid ${theme.border}` }}>
                    <b>{f.item?.id}</b> — {f.error}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

