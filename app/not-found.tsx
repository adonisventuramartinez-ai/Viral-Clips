import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page">
      <div className="card" style={{ maxWidth: 560, margin: "12vh auto", textAlign: "center" }}>
        <div style={{ fontSize: 44 }}>🔎</div>
        <h2 style={{ margin: "10px 0" }}>No encontramos esa página</h2>
        <p style={{ color: "var(--muted)", marginBottom: 18 }}>Puede que el clip se haya borrado o que el enlace esté viejo.</p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          <Link className="btn" href="/biblioteca">Ir a la biblioteca</Link>
          <Link className="btn ghost" href="/crear">Crear un clip</Link>
        </div>
      </div>
    </div>
  );
}
