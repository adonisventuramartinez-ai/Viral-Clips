export default function Ajustes() {
  const rows: [string, string, string][] = [
    ["Quién elige los clips", "LLM_PROVIDER", "groq (gratis) o anthropic"],
    ["Modelo de Groq", "GROQ_MODEL", "llama-3.3-70b-versatile"],
    ["Idioma del video", "LANGUAGE", "es"],
    ["Formato vertical", "CLIP_LAYOUT", "crop (llena la pantalla) o blur (fondo difuminado)"],
    ["Seguir a quien habla", "CLIP_FRAMING", "auto (sigue la cara) o center (fijo)"],
    ["Calidad del video", "CLIP_CRF", "18 (más bajo = más nítido y pesado)"],
    ["Encuadre del recorte", "CLIP_FOCUS_X", "0 = izquierda, 0.5 = centro, 1 = derecha"],
    ["Segundos por trozo (En vivo)", "SEGMENT_SECONDS", "120"],
    ["Puntaje mínimo En vivo", "LIVE_MIN_SCORE", "55"],
    ["Transcripción local", "WHISPER_MODEL", "small (solo si no usas Groq)"],
  ];
  return (
    <>
      <h1>Ajustes de IA</h1>
      <p className="sub">Por ahora estos ajustes se cambian en el archivo <code>worker/.env</code> y se aplican al reiniciar el worker.</p>
      <div className="card neon" style={{ maxWidth: 720 }}>
        {rows.map(([label, key, hint]) => (
          <div key={key} style={{ padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
            <b>{label}</b><br />
            <code>{key}</code> <span style={{ color: "var(--muted)", fontSize: 13 }}>· {hint}</span>
          </div>
        ))}
        <p className="sub" style={{ marginTop: 14, marginBottom: 0, fontSize: 13 }}>
          La cantidad de clips, la duración y la calidad se eligen en “Crear clips”.
        </p>
      </div>
    </>
  );
}
