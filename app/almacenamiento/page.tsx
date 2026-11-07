export default function Almacenamiento() {
  const used = 0.34, total = 1;
  return (
    <>
      <h1>Almacenamiento</h1>
      <p className="sub">Espacio usado por grabaciones, videos fuente y clips.</p>
      <div className="card" style={{ maxWidth: 640 }}>
        <p style={{ marginBottom: 10 }}>{used} GB de {total} GB</p>
        <div className="bar"><i style={{ width: `${(used / total) * 100}%` }} /></div>
        <div className="grid3" style={{ marginTop: 18 }}>
          <div><small className="sub">Grabaciones</small><p>0.21 GB</p></div>
          <div><small className="sub">Clips</small><p>0.11 GB</p></div>
          <div><small className="sub">Subidas</small><p>0.02 GB</p></div>
        </div>
        <button className="btn ghost sm" style={{ marginTop: 18 }}>Borrar grabaciones ya procesadas</button>
      </div>
    </>
  );
}
