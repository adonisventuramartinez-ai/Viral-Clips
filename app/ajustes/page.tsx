export default function Ajustes() {
  return (
    <>
      <h1>Ajustes de IA</h1>
      <p className="sub">Controla cómo la IA elige y presenta los clips.</p>
      <div className="card neon" style={{ maxWidth: 640 }}>
        <label>Estilo de clips</label>
        <select defaultValue="viral"><option value="viral">Viral (polémico, gracioso, impactante)</option><option value="edu">Educativo</option><option value="storytelling">Historias</option></select>
        <label>Idioma</label>
        <select defaultValue="es"><option value="es">Español</option><option value="en">English</option></select>
        <label>Cada cuánto revisa en vivo</label>
        <select defaultValue="2"><option value="1">1 min</option><option value="2">2 min</option><option value="5">5 min</option></select>
        <label>Llave de Claude (opcional, si usas la tuya)</label>
        <input type="password" placeholder="sk-ant-..." />
        <div style={{ marginTop: 18 }}><button className="btn">Guardar</button></div>
      </div>
    </>
  );
}
