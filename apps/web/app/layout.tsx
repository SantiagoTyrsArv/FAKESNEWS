import type { Metadata } from "next";
// Self-hosted via Fontsource so builds never depend on reaching Google Fonts.
import "@fontsource-variable/public-sans";
import "@fontsource-variable/newsreader";
import { MotionProvider } from "@/components/motion/motion-provider";
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

// Runs before first paint: only with JS and without reduced-motion does the
// page opt in to the pre-hidden "from" states in globals.css.
const motionClassScript = `try{if(!matchMedia("(prefers-reduced-motion: reduce)").matches)document.documentElement.classList.add("motion")}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: motionClassScript }} />
      </head>
      <body className="flex min-h-full flex-col">
        <MotionProvider>{children}</MotionProvider>
        <Toaster />
      </body>
    </html>
  );
}
