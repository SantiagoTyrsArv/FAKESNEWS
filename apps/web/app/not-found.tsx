import type { Metadata } from "next";
import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Página no encontrada",
};

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center px-4 py-5 sm:px-6">
        <Wordmark />
      </header>
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-start justify-center gap-6 px-4 py-16 sm:px-6">
        <p className="kicker">Error 404</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Esta página no existe
        </h1>
        <p className="max-w-[52ch] leading-relaxed text-muted-foreground">
          El enlace puede estar roto o la página se movió. Puedes volver al inicio o seguir
          verificando contenido.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button size="md" render={<Link href="/" />}>
            Volver al inicio
          </Button>
          <Button variant="outline" size="md" render={<Link href="/submit" />}>
            Verificar un contenido
          </Button>
        </div>
      </main>
    </div>
  );
}
