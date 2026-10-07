import type { ReactNode } from "react";
import { Wordmark } from "@/components/brand";

// Two-column layout for sign-in flows: the form on the right, and on the left
// a reminder of what the account is for, written as a highlighted claim.
export function AuthShell({
  title,
  description,
  step,
  children,
}: {
  title: string;
  description?: ReactNode;
  step?: { current: number; total: number };
  children: ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="hidden flex-col justify-between bg-ink p-10 text-white lg:flex">
        <Wordmark className="text-white" />
        <blockquote className="flex max-w-md flex-col gap-5">
          <p className="font-quote text-[1.75rem] leading-snug text-white/90">
            <span className="mark mark-insufficient text-ink">Cada conclusión lleva su cita.</span>{" "}
            Si ninguna fuente de confianza la respalda, el reporte lo dice.
          </p>
          <footer className="text-sm leading-relaxed text-white/60">
            FakesNews no declara noticias verdaderas o falsas: te muestra qué dicen las fuentes
            y qué tan confiables han sido.
          </footer>
        </blockquote>
        <p className="text-xs text-white/40">Verificación asistida por IA</p>
      </aside>

      <div className="flex flex-col px-4 py-6 sm:px-8">
        <Wordmark className="lg:hidden" />
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
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
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
