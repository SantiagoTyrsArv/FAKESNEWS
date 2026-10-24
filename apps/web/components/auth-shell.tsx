import type { ReactNode } from "react";
import Image from "next/image";
import { Wordmark } from "@/components/brand";
import { AuthCharacters, type CharacterState } from "@/components/auth/characters";

// Two-column layout for sign-in flows: the form on the right, and on the left
// a reminder of what the account is for, written as a highlighted claim over
// the collage illustration (darkened so the white text keeps its contrast).
// With `characters` (sign-in and sign-up) the left panel is instead a paper
// stage with the interactive characters, and on small screens a compact strip
// of them (≤ 96 px, wordmark inside) sits above the form, unless
// `mobileCharacters` is false: a page whose longest state would push the
// submit button below a 375×667 screen drops the strip (the form comes first).
export function AuthShell({
  title,
  description,
  step,
  characters,
  mobileCharacters = true,
  children,
}: Readonly<{
  title: string;
  description?: ReactNode;
  step?: { current: number; total: number };
  characters?: CharacterState;
  mobileCharacters?: boolean;
  children: ReactNode;
}>) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      {characters ? (
        <aside className="paper-texture relative isolate hidden flex-col overflow-hidden bg-paper px-10 pt-10 text-ink lg:flex dark:text-foreground">
          <Wordmark />
          <p className="mt-8 max-w-xs font-quote text-base leading-snug">
            <span className="mark mark-insufficient">Cada conclusión lleva su cita.</span>{" "}
            Si ninguna fuente de confianza la respalda, el reporte lo dice.
          </p>
          <div className="crew-box mx-auto mt-auto w-full max-w-[460px] pt-8">
            <AuthCharacters state={characters} />
          </div>
        </aside>
      ) : (
        <aside className="relative isolate hidden flex-col justify-between overflow-hidden bg-ink p-10 text-white lg:flex">
          <Image
            src="/media/auth.webp"
            alt=""
            fill
            sizes="45vw"
            className="-z-10 object-cover"
          />
          <div aria-hidden="true" className="absolute inset-0 -z-10 bg-ink/85" />
          <Wordmark className="text-white" />
          <blockquote className="flex max-w-md flex-col gap-5">
            <p className="font-quote text-[1.75rem] leading-snug text-white/90">
              <span className="mark mark-insufficient text-ink">Cada conclusión lleva su cita.</span>{" "}
              Si ninguna fuente de confianza la respalda, el reporte lo dice.
            </p>
            <footer className="text-sm leading-relaxed text-white/75">
              FakesNews no declara noticias verdaderas o falsas: te muestra qué dicen las fuentes
              y qué tan confiables han sido.
            </footer>
          </blockquote>
          <p className="text-xs text-white/60">Verificación asistida por IA</p>
        </aside>
      )}

      <div className="flex flex-col px-4 py-6 sm:px-8">
        {characters && mobileCharacters ? (
          <div className="paper-texture -mx-4 -mt-6 flex h-[88px] items-end justify-between gap-4 overflow-hidden bg-paper px-4 text-ink sm:-mx-8 sm:px-8 lg:hidden dark:text-foreground">
            <Wordmark className="self-center" />
            <div className="crew-box w-[106px] shrink-0">
              <AuthCharacters state={characters} compact />
            </div>
          </div>
        ) : (
          <Wordmark className="lg:hidden" />
        )}
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 py-10">
          <div className="flex flex-col gap-2">
            {step && (
              <div className="mb-2 flex items-center gap-2">
                {Array.from({ length: step.total }, (_, i) => (
                  <span
                    key={i}
                    aria-hidden="true"
                    className={
                      i < step.current
                        ? "h-1 w-8 rounded-full bg-primary"
                        : "h-1 w-8 rounded-full bg-border"
                    }
                  />
                ))}
                <span className="ml-1 text-xs font-medium text-muted-foreground">
                  Paso {step.current} de {step.total}
                </span>
              </div>
            )}
            <h1 className="font-heading text-3xl font-semibold tracking-tight">{title}</h1>
            {description && (
              <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
            )}
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
