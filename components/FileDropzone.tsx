"use client";

import { useEffect, useMemo, useRef, useState, DragEvent } from "react";
import { TipoContenido, validarArchivo } from "@/lib/facebook";

interface Theme {
  cardBg: string;
  border: string;
  text: string;
  subtext: string;
  accent: string;
  accentBg: string;
}

interface FileDropzoneProps {
  tipo: TipoContenido;
  archivo: File | null;
  onFileSelect: (file: File | null) => void;
  theme: Theme;
}

export default function FileDropzone({ tipo, archivo, onFileSelect, theme }: FileDropzoneProps) {
  const [arrastrando, setArrastrando] = useState(false);
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function procesarArchivo(file: File | null) {
    if (!file) {
      onFileSelect(null);
      setErrorArchivo(null);
      return;
    }
    const validacion = validarArchivo(file, tipo);
    if (!validacion.valido) {
      setErrorArchivo(validacion.error || "Archivo inválido");
      onFileSelect(null);
      return;
    }
    setErrorArchivo(null);
    onFileSelect(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setArrastrando(false);
    const file = e.dataTransfer.files?.[0] || null;
    procesarArchivo(file);
  }

  const previewUrl = useMemo(() => (archivo ? URL.createObjectURL(archivo) : null), [archivo]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${arrastrando ? theme.accent : theme.border}`,
          borderRadius: "8px",
          padding: archivo ? "12px" : "24px",
          textAlign: "center",
          cursor: "pointer",
          background: arrastrando ? theme.accentBg : theme.cardBg,
          transition: "all 0.15s",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={tipo === "foto" ? "image/*" : "video/*"}
          onChange={(e) => procesarArchivo(e.target.files?.[0] || null)}
          style={{ display: "none" }}
        />

        {!archivo ? (
          <>
            <div style={{ fontSize: "32px", marginBottom: "8px" }}>{tipo === "foto" ? "🖼️" : "🎬"}</div>
            <div style={{ fontSize: "14px", color: theme.text, fontWeight: 500 }}>
              Arrastra un archivo aquí o haz clic para seleccionar
            </div>
            <div style={{ fontSize: "12px", color: theme.subtext, marginTop: "4px" }}>
              {tipo === "foto" ? "JPG, PNG, GIF, WEBP (máx. 10MB)" : "MP4, MOV (según límites de Facebook)"}
            </div>
          </>
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: "12px", textAlign: "left" }}>
            {tipo === "foto" ? (
              <img
                src={previewUrl!}
                alt="preview"
                style={{ width: "64px", height: "64px", objectFit: "cover", borderRadius: "6px" }}
              />
            ) : (
              <video
                src={previewUrl!}
                style={{ width: "64px", height: "64px", objectFit: "cover", borderRadius: "6px" }}
                muted
              />
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 500,
                  color: theme.text,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {archivo.name}
              </div>
              <div style={{ fontSize: "12px", color: theme.subtext }}>
                {(archivo.size / (1024 * 1024)).toFixed(2)} MB
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                procesarArchivo(null);
              }}
              style={{
                background: "none",
                border: "none",
                fontSize: "18px",
                cursor: "pointer",
                color: theme.subtext,
              }}
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {errorArchivo && (
        <div style={{ color: "#c62828", fontSize: "12px", marginTop: "6px" }}>⚠️ {errorArchivo}</div>
      )}
    </div>
  );
}

