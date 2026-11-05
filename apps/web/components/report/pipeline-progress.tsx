import { Check } from "lucide-react";
import { STATUS_LABELS, type Submission, type SubmissionStatus } from "@/lib/cases";
import { cn } from "@/lib/utils";

const PIPELINE_STEPS: SubmissionStatus[] = [
  "queued",
  "ingesting",
  "transcribing",
  "extracting",
  "verifying",
  "scoring",
];

export function PipelineProgress({ submission }: Readonly<{ submission: Submission }>) {
  const steps = PIPELINE_STEPS.filter(
    (step) => step !== "transcribing" || submission.input_type === "video",
  );
  const currentIndex = steps.indexOf(submission.status);

  return (
    <section className="animated fadeIn grid gap-8 rounded-2xl border bg-card p-6 sm:p-8 md:grid-cols-2">
      <div className="flex flex-col gap-3">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Analizando el contenido</h1>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Esta página se actualiza sola. Puedes cerrarla: el reporte quedará en Mis casos.
        </p>
        <p className="mt-2 line-clamp-5 rounded-lg bg-muted/60 p-3 font-quote text-[0.95rem] leading-relaxed break-words whitespace-pre-wrap">
          {submission.raw_input}
        </p>
      </div>
      <ol className="flex flex-col gap-0.5" aria-label="Progreso del análisis">
        {steps.map((step, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          return (
            <li
              key={step}
              aria-current={active ? "step" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm",
                active && "bg-accent font-medium text-accent-foreground",
                !done && !active && "text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full border",
                  done && "border-primary bg-primary text-primary-foreground",
                  active && "border-primary",
                )}
              >
                {done && <Check className="size-3" aria-hidden="true" />}
                {active && <span className="size-2 animate-pulse rounded-full bg-primary" />}
              </span>
              {STATUS_LABELS[step]}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
