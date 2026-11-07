import ClipCard from "@/components/ClipCard";
import { demoClips } from "@/lib/demo";

export default function Biblioteca() {
  return (
    <>
      <h1>Biblioteca</h1>
      <p className="sub">Todos tus clips guardados, ordenados por potencial viral.</p>
      <div className="clips">
        {[...demoClips].sort((a, b) => b.score - a.score).map((c) => <ClipCard key={c.id} clip={c} />)}
      </div>
    </>
  );
}
