"use client";
import { useCallback, useEffect, useState } from "react";

export type Me = { username: string; display_name: string; avatar: string | null };

/** Quién soy: { me } con mi cuenta, o me = null si entré solo con la clave. `refreshMe()` avisa a todos (barra superior, Mi cuenta) que recarguen. */
export function useMe() {
  const [me, setMe] = useState<Me | null>(null);
  const [loaded, setLoaded] = useState(false);
  const load = useCallback(async () => {
    const r = await fetch("/api/cuenta", { cache: "no-store" }).catch(() => null);
    const j = await r?.json().catch(() => ({}));
    setMe(j?.user ?? null);
    setLoaded(true);
  }, []);
  useEffect(() => {
    load();
    window.addEventListener("cf-me", load);
    return () => window.removeEventListener("cf-me", load);
  }, [load]);
  return { me, loaded, reload: load };
}

export const refreshMe = () => window.dispatchEvent(new Event("cf-me"));
