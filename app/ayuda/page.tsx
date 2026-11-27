export default function Ayuda() {
  return (
    <>
      <h1>Ayuda</h1>
      <p className="sub">Respuestas rapidas.</p>
      <div className="grid2">
        <div className="card"><h4>Como creo clips de un video?</h4><p className="sub" style={{ marginTop: 8 }}>En "Crear clips" pega el link, elige cuantos clips y calidad, y toca Analizar video.</p></div>
        <div className="card"><h4>Como funciona En vivo?</h4><p className="sub" style={{ marginTop: 8 }}>Pega el link de un directo. La app graba, transcribe y busca momentos virales cada pocos minutos, usando tambien el chat.</p></div>
        <div className="card"><h4>Que significa "% viral"?</h4><p className="sub" style={{ marginTop: 8 }}>Una estimacion de la IA segun gancho, emocion, reaccion del chat y claridad del clip.</p></div>
        <div className="card"><h4>Que es "Pasar a narrado"?</h4><p className="sub" style={{ marginTop: 8 }}>Crea una version con voz narrando el contexto encima del clip.</p></div>
        <div className="card"><h4>Que es "Transformar"?</h4><p className="sub" style={{ marginTop: 8 }}>Convierte un video externo (TikTok, Instagram, MP4) en un clip vertical 1080x1920 con voz narradora, contexto, dramometro, encuesta A/B y tu logo. Anti-penalizacion para Facebook.</p></div>
        <div className="card"><h4>Que es "Crear con IA"?</h4><p className="sub" style={{ marginTop: 8 }}>Genera un video de 60 segundos desde un prompt de texto con Hugging Face. Elige estilo (realista, anime, cyberpunk, cartoon, 3D) y musica opcional. Necesita HF_TOKEN en worker/.env.</p></div>
      </div>
    </>
  );
}