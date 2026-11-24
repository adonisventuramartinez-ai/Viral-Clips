"use client";

import { motion, AnimatePresence } from "framer-motion";
import { TipoContenido } from "@/lib/facebook";

interface Theme {
  cardBg: string;
  border: string;
  text: string;
  subtext: string;
  accent: string;
}

interface PreviewModalProps {
  abierto: boolean;
  onClose: () => void;
  onConfirmar: () => void;
  titulo: string;
  mensaje: string;
  archivo: File | null;
  tipo: TipoContenido;
  paginasSeleccionadas: string[];
  theme: Theme;
}

export default function PreviewModal({
  abierto,
  onClose,
  onConfirmar,
  titulo,
  mensaje,
  archivo,
  tipo,
  paginasSeleccionadas,
  theme,
}: PreviewModalProps) {
  if (!abierto) return null;

  const previewUrl = archivo ? URL.createObjectURL(archivo) : null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
          padding: "16px",
        }}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          style={{
            background: theme.cardBg,
            borderRadius: "12px",
            maxWidth: "420px",
            width: "100%",
            maxHeight: "90vh",
            overflow: "auto",
          }}
        >
          <div
            style={{
              padding: "16px",
              borderBottom: `1px solid ${theme.border}`,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span style={{ fontWeight: 600, color: theme.text }}>👁️ Vista previa</span>
            <button
              onClick={onClose}
              style={{ background: "none", border: "none", fontSize: "18px", cursor: "pointer", color: theme.subtext }}
            >
              ✕
            </button>
          </div>

          {/* Mock de post estilo Facebook */}
          <div style={{ padding: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  background: "#1877f2",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "white",
                  fontSize: "16px",
                }}
              >
                f
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: "13px", color: theme.text }}>
                  {paginasSeleccionadas[0] || "Tu página"}
                  {paginasSeleccionadas.length > 1 && ` +${paginasSeleccionadas.length - 1} más`}
                </div>
                <div style={{ fontSize: "11px", color: theme.subtext }}>Ahora · 🌐</div>
              </div>
            </div>

            {titulo && (
              <div style={{ fontWeight: 600, fontSize: "14px", color: theme.text, marginBottom: "4px" }}>
                {titulo}
              </div>
            )}
            {mensaje && (
              <div style={{ fontSize: "13px", color: theme.text, marginBottom: "10px", whiteSpace: "pre-wrap" }}>
                {mensaje}
              </div>
            )}

            {previewUrl && (
              <div style={{ borderRadius: "8px", overflow: "hidden", background: "#000" }}>
                {tipo === "foto" ? (
                  <img src={previewUrl} alt="preview" style={{ width: "100%", display: "block" }} />
                ) : (
                  <video src={previewUrl} controls style={{ width: "100%", display: "block" }} />
                )}
              </div>
            )}
          </div>

          <div style={{ padding: "16px", borderTop: `1px solid ${theme.border}`, display: "flex", gap: "8px" }}>
            <button
              onClick={onClose}
              style={{
                flex: 1,
                padding: "10px",
                background: "transparent",
                border: `1px solid ${theme.border}`,
                borderRadius: "6px",
                color: theme.text,
                cursor: "pointer",
              }}
            >
              Editar
            </button>
            <button
              onClick={onConfirmar}
              style={{
                flex: 1,
                padding: "10px",
                background: theme.accent,
                border: "none",
                borderRadius: "6px",
                color: (theme as any).accentText || "white",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              🚀 Publicar ahora
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

