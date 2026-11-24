"use client";

import { useEffect, useRef, useState } from "react";

type EstadoAcceso = "cargando" | "pendiente" | "aprobado" | "rechazado" | "sin_login";

interface AccesoGateProps {
  token: string | null;
  // Se llama si Facebook dice que el token guardado ya no sirve
  onTokenInvalido?: () => void;
  children: React.ReactNode;
}

export default function AccesoGate({ token, onTokenInvalido, children }: AccesoGateProps) {
  const [estado, setEstado] = useState<EstadoAcceso>("cargando");
  const [codigo, setCodigo] = useState<string | null>(null);
  const [nombre, setNombre] = useState<string>("");
  const intervaloRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelado = false;

    async function verificar(t: string, primera: boolean) {
      try {
        // El servidor valida el token con Facebook y, si el usuario está aprobado, pone la cookie de sesión
        const res = await fetch("/api/fb/auth/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: t }),
        });
        const data = await res.json();
        if (cancelado) return;

        if (res.status === 401 || data.estado === "sin_login") {
          setEstado("sin_login");
          if (primera) onTokenInvalido?.();
          return;
        }
        if (data.nombre) setNombre(data.nombre);
        setCodigo(data.codigo_solicitud ?? null);
        setEstado(data.estado);

        if (data.estado === "pendiente" && !intervaloRef.current) {
          // Mientras esté pendiente, consulta cada 10 s por si el admin ya lo aprobó
          intervaloRef.current = setInterval(() => verificar(t, false), 10000);
        }
        if (data.estado !== "pendiente" && intervaloRef.current) {
          clearInterval(intervaloRef.current);
          intervaloRef.current = null;
        }
      } catch (e) {
        console.error(e);
      }
    }

    if (!token) {
      setEstado("sin_login");
    } else {
      setEstado("cargando");
      verificar(token, true);
    }

    return () => {
      cancelado = true;
      if (intervaloRef.current) {
        clearInterval(intervaloRef.current);
        intervaloRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (estado === "sin_login") {
    return <>{children}</>; // deja pasar a la pantalla de "Conectar con Facebook"
  }

  if (estado === "cargando") {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "sans-serif", color: "#5f6368" }}>
        Verificando acceso...
      </div>
    );
  }

  if (estado === "pendiente") {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5", fontFamily: "sans-serif", padding: "16px" }}>
        <div style={{ background: "white", padding: "32px", borderRadius: "8px", maxWidth: "380px", textAlign: "center", boxShadow: "0 1px 3px rgba(0,0,0,0.12)" }}>
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>⏳</div>
          <h2 style={{ margin: "0 0 8px 0", fontSize: "18px" }}>Hola, {nombre}</h2>
          <p style={{ color: "#5f6368", fontSize: "14px", marginBottom: "16px" }}>
            Tu acceso está pendiente de aprobación. Envía este código al administrador para activarlo:
          </p>
          <div style={{ fontSize: "28px", fontWeight: 700, letterSpacing: "4px", background: "#f8f9fa", padding: "12px", borderRadius: "8px", marginBottom: "12px" }}>
            {codigo}
          </div>
          <p style={{ fontSize: "12px", color: "#9aa0a6" }}>Esta pantalla se actualiza sola cada 10 segundos.</p>
        </div>
      </div>
    );
  }

  if (estado === "rechazado") {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5", fontFamily: "sans-serif", padding: "16px" }}>
        <div style={{ background: "white", padding: "32px", borderRadius: "8px", maxWidth: "380px", textAlign: "center" }}>
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>🚫</div>
          <h2 style={{ margin: "0 0 8px 0", fontSize: "18px" }}>Acceso no autorizado</h2>
          <p style={{ color: "#5f6368", fontSize: "14px" }}>
            El administrador no aprobó tu solicitud. Contáctalo si crees que es un error.
          </p>
        </div>
      </div>
    );
  }

  // aprobado
  return <>{children}</>;
}

