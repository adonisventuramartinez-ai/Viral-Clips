"use client";
import { useSwitches, type SwitchName } from "@/lib/useSwitches";

type Props = { name: SwitchName; title: string; desc: string; confirmOn?: string };

const ago = (iso: string | null) => (iso ? Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000)) : Infinity);

/** Tarjeta con el botón de encender/apagar. Dice si el worker ya lo aplicó, si está apagado o si es de una versión anterior. */
export default function SwitchCard({ name, title, desc, confirmOn }: Props) {
  const sw = useSwitches();
  const on = sw.isOn(name), want = sw.desired[name], real = sw.effective[name];
  const workerAlive = ago(sw.seenAt) < 180;
  const applied = real !== null && real === on;

  function toggle() {
    if (sw.busy) return;
    if (!on && confirmOn && !confirm(confirmOn)) return;
    sw.set(name, !on);
  }

  let status = "";
  let warn = false;
  if (!sw.ready) status = "Cargando…";
  else if (sw.seenAt === null) { status = "El worker todavía no ha avisado. Cuando lo prendas, el botón se aplica solo."; warn = true; }
  else if (!workerAlive) { status = "El worker está apagado: el botón se aplicará cuando lo prendas."; warn = true; }
  else if (!sw.switches) { status = "Tu worker es de una versión anterior: ejecuta INICIAR-SIEMPRE.bat para que este botón funcione."; warn = true; }
  else if (!applied) status = "Aplicando… el worker lo toma en unos segundos.";
  else status = `El worker confirma: ${real ? "encendido" : "apagado"}.`;

  return (
    <div className={`card ${on ? "neon" : ""}`} style={{ marginBottom: 18, display: "grid", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ minWidth: 220, flex: 1 }}>
          <b style={{ fontSize: 16 }}>{title}</b>
          <div><small style={{ color: "var(--muted)" }}>{desc}</small></div>
        </div>
        <button
          type="button" role="switch" aria-checked={on} aria-label={title} onClick={toggle} disabled={!sw.ready || sw.busy === name}
          style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: sw.busy === name ? "wait" : "pointer", background: "transparent", border: 0, color: "var(--text)", font: "inherit", fontWeight: 700, padding: 0 }}
        >
          <span style={{ width: 54, height: 30, borderRadius: 999, position: "relative", background: on ? "#12c46b" : "#2a2d52", transition: "background .2s", flex: "none" }}>
            <span style={{ position: "absolute", top: 3, left: on ? 27 : 3, width: 24, height: 24, borderRadius: "50%", background: "#fff", transition: "left .2s" }} />
          </span>
          <span style={{ minWidth: 92, textAlign: "left", color: on ? "#12c46b" : "var(--muted)" }}>{on ? "ENCENDIDO" : "APAGADO"}</span>
        </button>
      </div>
      {sw.err && <div className="banner" style={{ margin: 0 }}>{sw.err}</div>}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <small style={{ color: warn ? "#ff9a1f" : "var(--muted)" }}>{status}</small>
        {want !== null && sw.ready && (
          <button type="button" className="btn sm ghost" disabled={sw.busy === name} onClick={() => sw.set(name, null)} title="Deja de mandar el botón y vuelve a lo que diga worker/.env">
            Usar lo del .env
          </button>
        )}
      </div>
    </div>
  );
}
