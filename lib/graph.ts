// Versión de la Graph API en UN solo lugar. Para subir de versión basta con
// definir NEXT_PUBLIC_GRAPH_VERSION en Vercel (ej. v24.0), sin tocar código.
// Revisa https://developers.facebook.com/docs/graph-api/changelog cada ~6 meses.
import { limpiarEnv } from "./env";

export const GRAPH_VERSION = limpiarEnv(process.env.NEXT_PUBLIC_GRAPH_VERSION) || "v23.0";
export const GRAPH_BASE = `https://graph.facebook.com/${GRAPH_VERSION}`;
export const GRAPH_DIALOG = `https://www.facebook.com/${GRAPH_VERSION}/dialog/oauth`;

// URL pública de la app. Si no se define, se usa el origen de la petición.
export function appUrl(origenPeticion?: string): string {
  return (limpiarEnv(process.env.NEXT_PUBLIC_APP_URL) || origenPeticion || "").replace(/\/+$/, "");
}

// App ID / Secret de Facebook (servidor). Se limpian para que un espacio o salto de línea
// pegado por error en Vercel no haga que el login falle con "token de otra app".
export const fbAppId = () => limpiarEnv(process.env.FB_APP_ID);
export const fbAppSecret = () => limpiarEnv(process.env.FB_APP_SECRET);

