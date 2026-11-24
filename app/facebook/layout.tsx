import { Toaster } from "react-hot-toast";

export const metadata = {
  title: "Facebook - ClipForge",
  description: "Publica fotos, videos y reels en varias paginas de Facebook",
};

export default function FacebookLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          style: { fontSize: "14px" },
          success: { iconTheme: { primary: "#34a853", secondary: "white" } },
          error: { iconTheme: { primary: "#c62828", secondary: "white" } },
        }}
      />
    </>
  );
}