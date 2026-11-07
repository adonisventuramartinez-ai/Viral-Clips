"use client";
import { useEffect, useState } from "react";

const TOTAL_GB = 1; // plan gratis de Supabase Storage

export default function Almacenamiento() {
  const [data, setData] = useState<{ usedBytes: number; clips: number; demo?: boolean } | null>(null);

  useEffect(() => {
    fetch("/api/storage", { cache: "no-store" }).then((r) => r.json()).then(setData).catch(() => setData(null));
  }, []);

  const usedGb = (data?.usedBytes ?? 0) / 1073741824;
  return (
    <>
      <h1>Almacenamiento</h1>
      <p className="sub">Espacio que ocupan tus clips en Supabase Storage.</p>
      <div className="card" style={{ maxWidth: 640 }}>
        {!data ? (
          <p>Cargando…</p>
        ) : (
          <>
            <p style={{ marginBottom: 10 }}>{usedGb.toFixed(2)} GB de {TOTAL_GB} GB · {data.clips} clips</p>
            <div className="bar"><i style={{ width: `${Math.min(100, (usedGb / TOTAL_GB) * 100)}%` }} /></div>
            <p className="sub" style={{ marginTop: 14, marginBottom: 0, fontSize: 13 }}>
              El plan gratis de Supabase incluye 1 GB. Para borrar clips, hazlo desde Supabase → Storage → clips.
            </p>
          </>
        )}
      </div>
    </>
  );
}
