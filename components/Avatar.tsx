import { initials } from "@/lib/profile";

/** Foto de perfil redonda; si no hay foto, las iniciales sobre el degradado de la app. */
export default function Avatar({ name, src, size = 36 }: { name: string; src?: string | null; size?: number }) {
  const box = { width: size, height: size, borderRadius: "50%", flex: "none" as const };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={name} style={{ ...box, objectFit: "cover", border: "1px solid var(--line)" }} />;
  }
  return (
    <span aria-label={name} style={{ ...box, display: "inline-grid", placeContent: "center", background: "var(--grad)", color: "#fff", fontWeight: 700, fontSize: Math.round(size * 0.4) }}>
      {initials(name)}
    </span>
  );
}
