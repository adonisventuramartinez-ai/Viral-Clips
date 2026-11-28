"use client";
import { useEffect, useState } from "react";

const TOTAL_GB = 1; // plan gratis de Supabase Storage

type StorageInfo = {
  driver: string;
  endpointSet: boolean;
  accessKeySet: boolean;
  secretSet: boolean;
  bucket: string;
  region: string;
  probe: { ok: boolean; code?: string; error?: string };
};

export default function Almacenamiento() {
  const [data, setData] = useState<{ usedBytes: number; clips: number; demo?: boolean; storage?: StorageInfo } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/storage", { cache: "no-store" });
        const j = await r.json();
        if (!alive) return;
        if (!r.ok) throw new Error(j.error || "No se pudo cargar");
        setData(j);
      } catch (e: any) {
        if (alive) setErr(e?.message || "Error de conexión");
      }
    })();
    return () => { alive = false; };
  }, []);

  const usedGb = (data?.usedBytes ?? 0) / 1073741824;
  const s = data?.storage;
  const ready = s?.driver === "r2" ? s.endpointSet && s.accessKeySet && s.secretSet : true;

  return (
    <div className="page">
      <h1>Almacenamiento</h1>
      <p className="sub">Los clips se guardan en Tigris (gratis, sin tarjeta) y Supabase queda como respaldo automático.</p>

      {err && <div className="banner">⚠ {err}</div>}

      <div className="card" style={{ maxWidth: 760, marginBottom: 16 }}>
        {!data ? <p>Cargando…</p> : (
          <>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
              <span className="pill">Motor: {s?.driver === "r2" ? "Tigris / S3" : "Supabase"}</span>
              <span className={`pill ${s?.probe?.ok ? "green" : "ghost"}`}>{s?.probe?.ok ? "Conexión OK" : "Conexión fallida"}</span>
              {s && <span className="pill ghost">Bucket: {s.bucket}</span>}
              {s && <span className="pill ghost">Región: {s.region}</span>}
            </div>
            {s && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                <span className="pill ghost">Endpoint: {s.endpointSet ? "configurado" : "falta"}</span>
                <span className="pill ghost">Access Key: {s.accessKeySet ? "configurada" : "falta"}</span>
                <span className="pill ghost">Secret: {s.secretSet ? "configurado" : "falta"}</span>
              </div>
            )}
            {s && !s.probe.ok && (
              <div className="banner" style={{ marginBottom: 12 }}>
                ⚠ {s.probe.code || "Storage"}: {s.probe.error || "Sin detalle"}.
                {s.driver === "r2" && " Revisa las 6 variables en Vercel (Production) y vuelve a desplegar."}
              </div>
            )}
            {s && s.driver === "r2" && !ready && (
              <div className="banner" style={{ marginBottom: 12 }}>Faltan variables R2 en este deployment. El worker sí las tiene; la web no.</div>
            )}
            <p style={{ marginBottom: 10 }}>{usedGb.toFixed(2)} GB de {TOTAL_GB} GB de Supabase · {data.clips} clips</p>
            <div className="bar"><i style={{ width: `${Math.min(100, (usedGb / TOTAL_GB) * 100)}%` }} /></div>
            <p className="sub" style={{ marginTop: 14, marginBottom: 0, fontSize: 13 }}>
              Si ves <b>InvalidAccessKeyId</b> aquí, la llave de Vercel es vieja: actualízala y redeploya. Los secretos nunca se muestran en esta página.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
