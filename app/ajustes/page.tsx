export default function Ajustes() {
  const rows: [string, string, string][] = [
    ["Quién elige los clips", "LLM_PROVIDER", "groq (gratis) o anthropic"],
    ["Modelo de Groq", "GROQ_MODEL", "llama-3.3-70b-versatile"],
    ["Idioma del video", "LANGUAGE", "es"],
    ["Formato vertical", "CLIP_LAYOUT", "blur (fondo difuminado) o crop (recorte)"],
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
