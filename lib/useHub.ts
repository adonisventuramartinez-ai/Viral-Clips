"use client";
import { useCallback, useEffect, useState } from "react";

/** Lee /api/hub/<recurso> y deja recargar. */
export function useHub<T = any>(resource: string, query = "") {
  const [items, setItems] = useState<T[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    fetch(`/api/hub/${resource}${query}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => { if (j.error) setError(j.error); else { setError(""); setItems(j.items ?? []); } })
      .catch(() => setError("No se pudo conectar"));
  }, [resource, query]);
  useEffect(load, [load]);
  return { items, error, reload: load };
}

export async function postHub(resource: string, body: object): Promise<string | null> {
  const r = await fetch(`/api/hub/${resource}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  return r.ok ? null : j.error ?? "Error";
}
