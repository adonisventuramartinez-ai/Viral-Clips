import Ring from "@/components/Ring";
import ClipCard from "@/components/ClipCard";
import { demoClips, demoRejected, demoSteps } from "@/lib/demo";

export default function EnVivo() {
  return (
    <>
      <h1>En vivo</h1>
      <p className="sub">Graba un directo y va sacando clips mientras ocurre. Puedes dejar esta pantalla abierta.</p>

      <div className="card" style={{ marginBottom: 16, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input style={{ flex: 1, minWidth: 240 }} placeholder="Link del directo de YouTube" />
        <button className="btn">Empezar a grabar</button>
      </div>

      <div className="grid2">
        <div className="card red">
          <Ring time="30:24" />
          <div className="steps">
            {demoSteps.map((s) => (
              <div key={s.label} className={`step ${s.state}`}>
                <i className="dot" />
                <div><b>{s.label}</b>{s.detail && <span>{s.detail}</span>}</div>
              </div>
            ))}
          </div>
          <div className="why">
            <h4>Por qué no se eligieron</h4>
            <ul>
              {demoRejected.map((r) => (
                <li key={r.title}>{r.title} · {r.score}<span>{r.reason}</span></li>
              ))}
            </ul>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button className="btn sm ghost">Crear resumen</button>
            <button className="btn sm ghost">■ Parar</button>
          </div>
        </div>

        <div className="card neon">
          <h4 style={{ fontSize: 14, color: "var(--muted)" }}>Clips de este directo · {demoClips.length}</h4>
          <div className="clips" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
            {demoClips.map((c) => <ClipCard key={c.id} clip={c} />)}
          </div>
        </div>
      </div>
    </>
  );
}
