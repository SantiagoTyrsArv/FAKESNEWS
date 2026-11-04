"use client";

import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { Button } from "@/components/ui/button";

export default function Error({
  reset,
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center px-4 py-5 sm:px-6">
        <Wordmark />
      </header>
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-start justify-center gap-6 px-4 py-16 sm:px-6">
        <p className="kicker">Algo salió mal</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          No pudimos cargar esta página
        </h1>
        <p className="max-w-[52ch] leading-relaxed text-muted-foreground">
          Fue un error inesperado de nuestra parte, no de lo que enviaste. Reintenta y, si sigue
          fallando, vuelve al inicio.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button size="md" onClick={reset}>
            Reintentar
          </Button>
          <Button variant="outline" size="md" render={<Link href="/" />}>
            Volver al inicio
          </Button>
        </div>
      </main>
    </div>
  );
}
