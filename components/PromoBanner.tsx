"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

type Promo = { id: string; name: string; channel_url: string | null; message: string | null };

/** Banner de publicidad. Muestra una promo aprobada (promo_requests.active = true) o la invitación a publicitarse. */
export default function PromoBanner({ variant = "ad" }: { variant?: "ad" | "reach" }) {
  const [promo, setPromo] = useState<Promo | null>(null);
  useEffect(() => {
    fetch("/api/hub/promos").then((r) => r.json()).then((j) => {
      const list: Promo[] = j.items ?? [];
      if (list.length) setPromo(list[Math.floor(Math.random() * list.length)]);
    }).catch(() => {});
  }, []);

  if (promo) {
    return (
      <div className="promo">
        <div className="ico">📺</div>
        <div><b>{promo.name}</b><small>{promo.message || "Canal recomendado de la comunidad"}</small></div>
        <a className="go" href={promo.channel_url || "/promo"} target="_blank" rel="noreferrer">Ver canal →</a>
      </div>
    );
  }
  return (
    <div className="promo">
      <div className="ico">{variant === "ad" ? "📣" : "🚀"}</div>
      <div>
        <b>{variant === "ad" ? "PUBLICITATE AQUÍ" : "¿QUERÉS MÁS VISTAS?"}</b>
        <small>{variant === "ad" ? "Mostrá tu canal, marca o servicio a toda la comunidad" : "Tu publicidad en el primero que ven los usuarios"}</small>
      </div>
      <Link className="go" href="/promo">{variant === "ad" ? "Ver cómo →" : "Publicitate →"}</Link>
    </div>
  );
}
