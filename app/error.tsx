"use client";
import { useEffect } from "react";
import Link from "next/link";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error("Error en la interfaz:", error); }, [error]);
  return (
    <div className="page">
      <div className="card" style={{ maxWidth: 640, margin: "10vh auto", textAlign: "center" }}>
        <div style={{ fontSize: 44 }}>🛠️</div>
        <h2 style={{ margin: "10px 0" }}>Algo salió mal</h2>
        <p style={{ color: "var(--muted)", marginBottom: 18 }}>
          No se perdió nada: vuelve a intentarlo. Si sigue pasando, revisa la cola del worker.
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          <button className="btn" onClick={reset}>Reintentar</button>
          <Link className="btn ghost" href="/cola">Ver la cola</Link>
          <Link className="btn ghost" href="/biblioteca">Ir a la biblioteca</Link>
        </div>
        {error.digest && <small style={{ display: "block", color: "var(--muted2)", marginTop: 14 }}>Ref: {error.digest}</small>}
      </div>
    </div>
  );
}
