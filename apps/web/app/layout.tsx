import type { Metadata } from "next";
// Self-hosted via Fontsource so builds never depend on reaching Google Fonts.
import "@fontsource-variable/public-sans";
import "@fontsource-variable/newsreader";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "FakesNews: verifica antes de compartir",
    template: "%s | FakesNews",
  },
  description:
    "Verificación asistida por IA de noticias sospechosas, con citas de fuentes de confianza y su historial de confiabilidad.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
