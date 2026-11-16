"use client";
import { useCallback, useEffect, useState } from "react";

export type SwitchName = "discover" | "auto_queue";
type Pair = Record<SwitchName, boolean | null>;
export type SwitchState = { desired: Pair; effective: Pair; switches: boolean; networks: string[]; seenAt: string | null };

const EMPTY: SwitchState = { desired: { discover: null, auto_queue: null }, effective: { discover: null, auto_queue: null }, switches: false, networks: [], seenAt: null };

/** Lee los botones (/api/interruptores) y los refresca solos cada 8 s para ver cuándo el worker los aplica. */
export function useSwitches() {
  const [st, setSt] = useState<SwitchState>(EMPTY);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState<SwitchName | null>(null);

  const load = useCallback(async () => {
    const r = await fetch("/api/interruptores", { cache: "no-store" }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) { setErr(j?.error ?? "No se pudo conectar"); return; }
    setErr(""); setSt({ ...EMPTY, ...j }); setReady(true);
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load]);

  /** value: true/false = botón; null = volver a lo que diga el .env. */
  const set = useCallback(async (name: SwitchName, value: boolean | null) => {
    setBusy(name); setErr("");
    setSt((s) => ({ ...s, desired: { ...s.desired, [name]: value } }));   // se ve el cambio al instante
    const r = await fetch("/api/interruptores", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [name]: value }) }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    if (!r?.ok) setErr(j?.error ?? "No se pudo guardar");
    setBusy(null);
    await load();
  }, [load]);

  /** Encendido o apagado como se muestra: lo que pediste en la web, y si nunca lo tocaste, lo que hace el worker. */
  const isOn = (n: SwitchName) => st.desired[n] ?? st.effective[n] ?? false;
  return { ...st, ready, err, busy, set, isOn };
}
