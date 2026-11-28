export default function Ayuda() {
  return (
    <>
      <h1>Ayuda</h1>
      <p className="sub">Respuestas rápidas.</p>
      <div className="grid2">
        <div className="card"><h4>¿Cómo creo clips de un video?</h4><p className="sub" style={{ marginTop: 8 }}>En “Crear clips” pega el link, elige cuántos clips y calidad, y toca Analizar video.</p></div>
        <div className="card"><h4>¿Cómo funciona En vivo?</h4><p className="sub" style={{ marginTop: 8 }}>Pega el link de un directo. La app graba, transcribe y busca momentos virales cada pocos minutos, usando también el chat.</p></div>
        <div className="card"><h4>¿Qué significa “% viral”?</h4><p className="sub" style={{ marginTop: 8 }}>Una estimación de la IA según gancho, emoción, reacción del chat y claridad del clip.</p></div>
        <div className="card"><h4>¿Qué es “Pasar a narrado”?</h4><p className="sub" style={{ marginTop: 8 }}>Crea una versión con voz narrando el contexto encima del clip.</p></div>
      </div>
    </>
  );
}
