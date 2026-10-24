"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { Curtain } from "@/components/landing/curtain";
import { HeroMedia } from "@/components/landing/hero-media";
import { Marquee } from "@/components/landing/marquee";
import { SourcesSection } from "@/components/landing/sources-section";
import { useLandingMotion } from "@/components/landing/use-landing-motion";
import { Button } from "@/components/ui/button";
import { VERDICTS, VERDICT_ORDER, VerdictLabel } from "@/components/verdict";
import { me, type UserResponse } from "@/lib/auth";
import type { Verdict } from "@/lib/cases";
import { cn } from "@/lib/utils";

// The hero is a worked example: a viral message as a fact-checker would mark
// it up, each claim highlighted by verdict with its note in the margin.
const SAMPLE: { text: string; verdict?: Verdict; note?: string }[] = [
  { text: "URGENTE, reenvía a todos tus grupos: " },
  {
    text: "el Ministerio de Salud confirmó ayer 12 casos nuevos en la capital",
    verdict: "SUPPORTED",
    note: "Dos fuentes independientes publican la misma cifra.",
  },
  { text: ", y " },
  {
    text: "desde el lunes cerrarán todos los colegios del país",
    verdict: "CONTRADICTED",
    note: "El comunicado oficial dice que las clases siguen.",
  },
  { text: ". Además, " },
  {
    text: "el agua del grifo ya estaría contaminada",
    verdict: "INSUFFICIENT",
    note: "Ninguna fuente de confianza lo menciona todavía.",
  },
  { text: "." },
];

// Each step has its collage illustration in /public/media (see PROMPTS.md).
const STEPS = [
  {
    title: "Pega el contenido",
    body: "Un texto, el enlace a un artículo o un video. Extraemos el texto o transcribimos el audio.",
  },
  {
    title: "Separamos las afirmaciones",
    body: "Solo los hechos comprobables. Las opiniones y las predicciones se dejan fuera.",
  },
  {
    title: "Las contrastamos con fuentes",
    body: "Cada afirmación se busca en medios y organismos de confianza. Toda cita se comprueba antes de mostrarse.",
  },
  {
    title: "Recibes el reporte",
    body: "Qué respalda cada fuente, qué contradice y qué tan confiable ha sido en casos anteriores.",
  },
];

export default function Home() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [checked, setChecked] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useLandingMotion(root);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecked(true));
  }, []);

  const claims = SAMPLE.filter((part) => part.verdict);

  return (
    <div ref={root} className="flex min-h-screen flex-col">
      <Curtain />
      <header
        data-enter="header"
        className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-5 sm:px-6"
      >
        <Wordmark />
        {/* Hidden until the session is known, only when JS can reveal it. */}
        <nav className={cn("flex items-center gap-2 transition-opacity", !checked && "[.js_&]:opacity-0")}>
          <Button variant="ghost" size="sm" render={<Link href="/sources" />}>
            Fuentes
          </Button>
          {user ? (
            <Button size="sm" render={<Link href="/history" />}>
              Mis casos
            </Button>
          ) : (
            <Button variant="outline" size="sm" render={<Link href="/login" />}>
              Iniciar sesión
            </Button>
          )}
        </nav>
      </header>

      <main className="flex flex-1 flex-col">
        <section className="mx-auto grid w-full max-w-6xl gap-12 px-4 pt-8 pb-16 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:items-center lg:gap-16 lg:pt-16 lg:pb-24">
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-3">
              <p data-enter="kicker" className="kicker">
                Verificación de noticias
              </p>
              <h1 className="font-heading text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
                Antes de reenviarlo, mira qué dicen las fuentes.
              </h1>
            </div>
            <p data-enter="lede" className="max-w-[46ch] text-lg leading-relaxed text-pretty text-muted-foreground">
              FakesNews separa un mensaje en afirmaciones comprobables y busca cada una en medios
              y organismos de confianza. No te damos un “verdadero” o “falso”: te damos las citas.
            </p>
            <div data-enter="actions" className="flex flex-wrap gap-3">
              {checked && user ? (
                <>
                  <Button
                    data-magnetic="0.35"
                    size="lg"
                    className="h-11 px-5 text-[0.95rem]"
                    render={<Link href="/submit" />}
                  >
                    Verificar un contenido
                  </Button>
                  <Button
                    data-magnetic="0.35"
                    size="lg"
                    variant="outline"
                    className="h-11 px-5 text-[0.95rem]"
                    render={<Link href="/history" />}
                  >
                    Ver mis casos
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    data-magnetic="0.35"
                    size="lg"
                    className="h-11 px-5 text-[0.95rem]"
                    render={<Link href="/register" />}
                  >
                    Crear una cuenta gratis
                  </Button>
                  <Button
                    data-magnetic="0.35"
                    size="lg"
                    variant="outline"
                    className="h-11 px-5 text-[0.95rem]"
                    render={<Link href="/login" />}
                  >
                    Ya tengo cuenta
                  </Button>
                </>
              )}
            </div>
            {checked && user && (
              <p className="text-sm text-muted-foreground">Sesión iniciada como {user.email}</p>
            )}
          </div>

          <HeroMedia>
            <figure
              data-tilt="3d"
              className="cutout relative rounded-xl border bg-card p-6 [--cutout-rotate:-1.2deg] sm:p-8"
            >
              <figcaption className="mb-4 flex items-center justify-between gap-3 text-sm text-muted-foreground">
                <span>Mensaje reenviado muchas veces</span>
                <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs">Ejemplo</span>
              </figcaption>
              <p className="font-quote text-xl leading-[1.7] sm:text-[1.4rem]">
                {SAMPLE.map((part) => {
                  if (!part.verdict) return <span key={part.text}>{part.text}</span>;
                  const index = claims.indexOf(part);
                  return (
                    <span
                      key={part.text}
                      className={cn("mark mark-draw", VERDICTS[part.verdict].mark)}
                      style={{ "--mark-delay": `${300 + index * 450}ms` } as React.CSSProperties}
                    >
                      {part.text}
                      <sup className="ml-0.5 font-sans text-xs font-bold text-muted-foreground">
                        {index + 1}
                      </sup>
                    </span>
                  );
                })}
              </p>
              <ol className="mt-6 flex flex-col gap-3 border-t pt-5">
                {claims.map((claim, index) => (
                  <li key={claim.text} className="grid grid-cols-[1.25rem_1fr] gap-x-2 gap-y-0.5">
                    <span className="pt-0.5 text-xs font-bold text-muted-foreground">{index + 1}</span>
                    <VerdictLabel verdict={claim.verdict!} />
                    <span />
                    <span className="text-sm text-muted-foreground">{claim.note}</span>
                  </li>
                ))}
              </ol>
            </figure>
          </HeroMedia>
        </section>

        <Marquee />

        <section className="torn-top bg-card">
          <div className="mx-auto grid w-full max-w-6xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,7fr)]">
            <div className="flex flex-col gap-3">
              <p className="kicker">Paso a paso</p>
              <h2 className="font-heading text-3xl font-semibold tracking-tight text-balance">
                Cómo se arma un reporte
              </h2>
              <p className="max-w-[40ch] leading-relaxed text-muted-foreground">
                Tarda entre uno y tres minutos. Puedes cerrar la página: el caso queda guardado en
                tu historial.
              </p>
            </div>
            <ol className="grid gap-x-10 gap-y-12 sm:grid-cols-2">
              {STEPS.map((step, i) => (
                <li key={step.title} data-reveal className="flex flex-col gap-6">
                  <div
                    data-tilt="3d"
                    className="cutout overflow-hidden rounded-lg border bg-paper"
                    style={{ "--cutout-rotate": i % 2 ? "1deg" : "-1deg" } as React.CSSProperties}
                  >
                    <Image
                      src={`/media/step-${i + 1}.webp`}
                      alt=""
                      data-parallax
                      width={800}
                      height={600}
                      sizes="(min-width: 1152px) 300px, (min-width: 640px) 45vw, 100vw"
                      className="h-auto w-full"
                    />
                  </div>
                  <div className="flex gap-4">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-bold text-accent-foreground">
                      {i + 1}
                    </span>
                    <div className="flex flex-col gap-1">
                      <h3 className="font-semibold">{step.title}</h3>
                      <p className="text-sm leading-relaxed text-muted-foreground">{step.body}</p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <SourcesSection />

        <section className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,7fr)]">
          <h2 className="font-heading text-3xl font-semibold tracking-tight text-balance">
            Tres resultados posibles por afirmación
          </h2>
          <dl className="flex flex-col divide-y">
            {VERDICT_ORDER.map((verdict) => (
              <div key={verdict} data-reveal className="grid gap-1 py-4 first:pt-0 sm:grid-cols-[14rem_1fr] sm:gap-6">
                <dt>
                  <VerdictLabel verdict={verdict} />
                </dt>
                <dd className="text-sm leading-relaxed text-muted-foreground">
                  {verdict === "SUPPORTED" &&
                    "Fuentes de confianza publican información que coincide con la afirmación."}
                  {verdict === "CONTRADICTED" &&
                    "Fuentes de confianza publican información que la desmiente."}
                  {verdict === "INSUFFICIENT" &&
                    "No hay citas comprobables. Puede ser reciente, local o simplemente falsa: falta evidencia para decirlo."}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </main>

      <footer className="rule-double-top">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-muted-foreground sm:px-6">
          <span>FakesNews es una herramienta de apoyo. Lee las fuentes antes de sacar conclusiones.</span>
          <Link href="/sources" className="underline-offset-4 hover:text-foreground hover:underline">
            Confiabilidad de las fuentes
          </Link>
        </div>
      </footer>
    </div>
  );
}
