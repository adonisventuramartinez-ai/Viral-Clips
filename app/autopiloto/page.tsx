"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

type Page = { id: string; name: string; project?: string; projectId?: number };
type Project = { id: number; nombre: string; paginas: { id: string; name: string }[]; error?: string };
type Config = { enabled: boolean; page_ids: string[]; auto_approve: boolean; max_per_run: number; updated_at?: string | null };
type Data = {
  config: Config;
  projects: Project[];
  pages: Page[];
  status: { savedAt: string | null; workerSyncsEvery: string; queueEvery: string };
  error?: string;
};

export default function Autopiloto() {
  const [data, setData] = useState<Data | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [maxPerRun, setMaxPerRun] = useState(5);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    const r = await fetch("/api/autopiloto", { cache: "no-store" }).catch(() => null);
    const j: Data | { error: string } = (await r?.json().catch(() => ({}))) as any;
    if (!r?.ok) {
      setErr((j as any)?.error ?? "No se pudo consultar el piloto");
      return;
    }
    const d = j as Data;
    setErr("");
    setData(d);
    setSelected(new Set(d.config.page_ids ?? []));
    setMaxPerRun(d.config.max_per_run ?? 5);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const allPages = useMemo(() => data?.pages ?? [], [data]);

  async function act(action: string, extra: Record<string, unknown> = {}) {
    setBusy(action);
    setNote("");
    const r = await fetch("/api/autopiloto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, page_ids: [...selected], max_per_run: maxPerRun, ...extra }),
    }).catch(() => null);
    const j: any = await r?.json().catch(() => ({}));
    setBusy("");
    if (!r?.ok) {
      setErr(j?.error ?? "No se pudo guardar");
      return;
    }
    setErr("");
    const warnings = (j?.warnings ?? []).length ? ` · avisos: ${(j.warnings as string[]).join("; ")}` : "";
    setNote(
      action === "encender"
        ? `Piloto encendido en ${j?.page_ids?.length ?? selected.size} página(s). El worker lo toma en ~15 s.${warnings}`
        : action === "apagar"
          ? `Piloto apagado.${warnings}`
          : action === "encolar"
            ? `Config guardada. El worker encola lo listo en ~2 min.${warnings}`
            : `Páginas guardadas.${warnings}`,
    );
    await load();
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const st = data?.status;
  const cfg = data?.config;

  return (
    <>
      <h1>🤖 Piloto automático</h1>
      <p className="sub">
        Un botón y listo: saca clips de tus fuentes, los aprueba, los programa y los publica solo en todas las páginas que elijas de tus cuentas conectadas. Varios proyectos, un solo sistema.
      </p>
      {err && <div className="banner">{err}</div>}
      {note && <div className="card" style={{ borderColor: "var(--cyan2)", color: "var(--cyan2)" }}>{note}</div>}

      <div className="card" style={{ display: "flex", justifyContent: "space-between", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <b style={{ fontSize: 18 }}>{cfg?.enabled ? "🟢 Piloto ENCENDIDO" : "⚪ Piloto APAGADO"}</b>
          <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
            {st?.savedAt ? `Guardado: ${new Date(st.savedAt).toLocaleString()}` : "Aún no se guardó configuración"}
          </div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
            El worker lee el cambio cada {st?.workerSyncsEvery ?? "15 s"} y encola cada {st?.queueEvery ?? "2 min"} · páginas marcadas: {cfg?.page_ids?.length ?? 0}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn" disabled={!!busy || !allPages.length} onClick={() => act(cfg?.enabled ? "config" : "encender")}>
            {busy === "encender" ? "Encendiendo…" : busy === "config" ? "Guardando…" : cfg?.enabled ? "💾 Guardar páginas" : "🚀 Encender piloto"}
          </button>
          <button className="btn ghost" disabled={!!busy || !cfg?.enabled} onClick={() => act("apagar")}>⏸ Apagar</button>
          <button className="btn ghost" disabled={!!busy || !selected.size} onClick={() => act("encolar")}>⚡ Publicar lo listo ya</button>
        </div>
      </div>

      {!data?.projects?.length && (
        <div className="banner">
          No hay cuentas de Facebook conectadas. Conecta tu cuenta en el menú <Link href="/facebook" style={{ color: "var(--cyan2)" }}>Facebook</Link> y vuelve aquí.
        </div>
      )}

      <h3 style={{ marginTop: 20 }}>Proyectos y páginas</h3>
      <p style={{ fontSize: 13, color: "var(--muted)", marginTop: -8 }}>
        Marca las páginas donde debe publicarse cada clip. Puedes tener varios proyectos y varias páginas por proyecto.
      </p>
      <div style={{ display: "grid", gap: 10 }}>
        {(data?.projects ?? []).map((p) => (
          <div key={p.id} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
              <b>📁 {p.nombre}</b>
              <small style={{ color: p.error ? "#ef4444" : "var(--muted)" }}>{p.error ?? `${p.paginas.length} página(s)`}</small>
            </div>
            <div style={{ display: "grid", gap: 6, marginTop: 10 }}>
              {p.paginas.map((page) => (
                <label key={page.id} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
                  <input type="checkbox" checked={selected.has(page.id)} onChange={() => toggle(page.id)} style={{ width: 17, height: 17 }} />
                  📘 {page.name} <small style={{ color: "var(--muted)" }}>· {page.id}</small>
                </label>
              ))}
              {!p.paginas.length && !p.error && <small style={{ color: "var(--muted)" }}>Esta cuenta no tiene páginas.</small>}
            </div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 18, display: "grid", gap: 8 }}>
        <b>¿Cómo va a publicar?</b>
        <small style={{ color: "var(--muted)" }}>
          Los clips pasan por Hacerlo viral, se aprueban solos y entran en la cola del worker en los mejores horarios aprendidos. Cada clip sale en cada página marcada, con una separación de 45 segundos entre páginas para no parecer spam.
        </small>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
          Máximo de clips por tanda:{" "}
          <input
            type="number" min={1} max={25} value={maxPerRun}
            style={{ width: 70 }} disabled={!!busy}
            onChange={(e) => setMaxPerRun(Math.max(1, Math.min(25, Number(e.target.value) || 5)))}
          />
        </label>
        <small style={{ color: "var(--muted)" }}>
          Corre <code>supabase/migrations/0020_autopiloto.sql</code> en <b>las dos Supabase</b>: la de la web (donde está tu cuenta de Facebook) y la del worker (donde están los clips). La firma usa la misma llave R2/Tigris que ya configuramos; abre una vez /almacenamiento y comprueba que diga Conexión OK.
        </small>
      </div>
    </>
  );
}
