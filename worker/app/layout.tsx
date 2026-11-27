import "./globals.css";
import type { Metadata } from "next";
import Nav from "@/components/Nav";
import { supabaseConfigured } from "@/lib/supabase";

export const metadata: Metadata = { title: "ClipForge · clips virales con IA", description: "Convierte podcasts y directos en clips verticales virales." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="shell">
          <Nav />
          {!supabaseConfigured && (
            <div className="banner" style={{ marginTop: 18 }}>
              Modo demo: Supabase no está conectado. Copia <code>.env.example</code> a <code>.env.local</code> y agrega tus llaves.
            </div>
          )}
          {children}
        </div>
      </body>
    </html>
  );
}
