import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import { supabaseConfigured } from "@/lib/supabase";

export const metadata: Metadata = { title: "ClipForge · convertí tus streams en clips virales", description: "Vertical, con subtítulos y listo para TikTok, Reels y Shorts." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="app">
          <Sidebar />
          <div className="main">
            <Topbar />
            <div className="page">
              {!supabaseConfigured && (
                <div className="banner">Modo demo: Supabase no está conectado. Copia <code>.env.example</code> a <code>.env.local</code> y agrega tus llaves.</div>
              )}
              {children}
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
