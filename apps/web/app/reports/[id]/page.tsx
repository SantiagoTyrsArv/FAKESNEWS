"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, ExternalLink } from "lucide-react";
import { AppShell, LoadingLine } from "@/components/app-shell";
import {
  ScoreMeter,
  VERDICTS,
  VERDICT_ORDER,
  VerdictBar,
  VerdictLabel,
} from "@/components/verdict";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  getReport,
  getSubmission,
  INPUT_TYPE_LABELS,
  STATUS_LABELS,
  TERMINAL_STATUSES,
  type Report,
  type ReportClaim,
  type ReportEvidence,
  type Stance,
  type Submission,
  type SubmissionStatus,
} from "@/lib/cases";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 2000;
// A bit over the worker's job timeout (PIPELINE_JOB_TIMEOUT_SECONDS, 15 min):
// past it the case should already be done or failed, so stop polling instead
// of spinning forever. Measured from created_at, so a reload doesn't reset it.
const STALE_AFTER_MS = 16 * 60 * 1000;

const PIPELINE_STEPS: SubmissionStatus[] = [
  "queued",
  "ingesting",
  "transcribing",
  "extracting",
  "verifying",
  "scoring",
];

const STANCE_STYLES: Record<Stance, { label: string; className: string }> = {
  supports: { label: "Respalda", className: "bg-supported-tint text-supported" },
  contradicts: { label: "Contradice", className: "bg-contradicted-tint text-contradicted" },
  neutral: { label: "Neutral", className: "bg-muted text-muted-foreground" },
};

export default function ReportPage({ params }: PageProps<"/reports/[id]">) {
  const { id } = use(params);
  const router = useRouter();
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const current = await getSubmission(id);
        if (cancelled) return;
        setSubmission(current);

        if (current.status === "done") {
          const fullReport = await getReport(id);
          if (!cancelled) setReport(fullReport);
          return;
        }
        if (!TERMINAL_STATUSES.includes(current.status)) {
          if (Date.now() - new Date(current.created_at).getTime() > STALE_AFTER_MS) {
            setStale(true);
            return;
          }
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login");
        } else if (err instanceof ApiError && err.status === 404) {
          setError("No existe un caso con este enlace en tu cuenta.");
        } else {
          setError("No se pudo cargar el caso. Reintentando…");
          timer = setTimeout(poll, POLL_INTERVAL_MS * 2);
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id, router]);

  return (
    <AppShell>
      <Link
        href="/history"
        className="-mb-4 inline-flex w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Mis casos
      </Link>

      {error && !report && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!submission && !error && <LoadingLine />}

      {submission && !report && submission.status !== "failed" && !stale && (
        <PipelineProgress submission={submission} />
      )}

      {stale && submission?.status !== "failed" && !report && (
        <section className="flex flex-col items-start gap-4 rounded-2xl border bg-card p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight">Este análisis está tardando demasiado</h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Lleva más tiempo del esperado sin terminar. Recarga la página en unos minutos o envía el
            caso de nuevo.
          </p>
          <Button className="h-10 px-4" render={<Link href="/submit" />}>
            Enviar otro caso
          </Button>
        </section>
      )}

      {submission?.status === "failed" && (
        <section className="flex flex-col items-start gap-4 rounded-2xl border bg-card p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight">No pudimos terminar este análisis</h1>
          <Alert variant="destructive">
            <AlertDescription>
              {submission.error ?? "Error desconocido en el procesamiento."}
            </AlertDescription>
          </Alert>
          <p className="text-sm text-muted-foreground">
            Si enviaste un enlace, comprueba que sea público o prueba pegando el texto directamente.
          </p>
          <Button className="h-10 px-4" render={<Link href="/submit" />}>
            Enviar otro caso
          </Button>
        </section>
      )}

      {report && <ReportView report={report} />}
    </AppShell>
  );
}

function PipelineProgress({ submission }: { submission: Submission }) {
  const steps = PIPELINE_STEPS.filter(
    (step) => step !== "transcribing" || submission.input_type === "video",
  );
  const currentIndex = steps.indexOf(submission.status);

  return (
    <section className="grid gap-8 rounded-2xl border bg-card p-6 sm:p-8 md:grid-cols-2">
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold tracking-tight">Analizando el contenido</h1>
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

function ReportView({ report }: { report: Report }) {
  const { submission, summary, claims, disclaimer } = report;
  const counts = {
    SUPPORTED: summary.supported,
    CONTRADICTED: summary.contradicted,
    INSUFFICIENT: summary.insufficient,
  };

  return (
    <>
      <section className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            Reporte de credibilidad ({INPUT_TYPE_LABELS[submission.input_type].toLowerCase()}),
            enviado el{" "}
            {new Date(submission.created_at).toLocaleString("es", {
              dateStyle: "long",
              timeStyle: "short",
            })}
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-balance sm:text-3xl">
            {summary.total_claims === 0
              ? "No encontramos afirmaciones comprobables"
              : summary.total_claims === 1
                ? "Revisamos 1 afirmación"
                : `Revisamos ${summary.total_claims} afirmaciones`}
          </h1>
        </div>

        <blockquote className="max-h-56 overflow-y-auto rounded-2xl border bg-card p-5 font-quote text-[1.05rem] leading-[1.7] break-words whitespace-pre-wrap sm:p-6">
          {submission.raw_input}
        </blockquote>

        {summary.total_claims > 0 && (
          <div className="flex flex-col gap-3">
            <VerdictBar counts={counts} />
            <ul className="flex flex-wrap gap-x-6 gap-y-2">
              {VERDICT_ORDER.map((v) => {
                const Icon = VERDICTS[v].icon;
                return (
                  <li key={v} className="flex items-center gap-2 text-sm">
                    <Icon className={cn("size-4", VERDICTS[v].text)} aria-hidden="true" />
                    <span className="font-semibold tabular-nums">{counts[v]}</span>
                    <span className="text-muted-foreground">{VERDICTS[v].plural}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <p className="border-l-2 border-primary pl-4 text-sm leading-relaxed text-muted-foreground">
          {disclaimer}
        </p>
      </section>

      {claims.length === 0 ? (
        <p className="rounded-2xl border border-dashed p-6 text-sm leading-relaxed text-muted-foreground">
          El contenido no tiene hechos comprobables: las opiniones y las predicciones se descartan.
        </p>
      ) : (
        <ol className="flex flex-col gap-5">
          {claims.map((claim, index) => (
            <ClaimCard key={claim.id} claim={claim} index={index + 1} />
          ))}
        </ol>
      )}

      <div className="flex flex-wrap gap-3 border-t pt-6">
        <Button className="h-10 px-4" render={<Link href="/submit" />}>
          Verificar otro contenido
        </Button>
        <Button variant="outline" className="h-10 px-4" render={<Link href="/sources" />}>
          Cómo medimos a las fuentes
        </Button>
      </div>
    </>
  );
}

function ClaimCard({ claim, index }: { claim: ReportClaim; index: number }) {
  const verdict = VERDICTS[claim.verdict];

  return (
    <li className="flex flex-col gap-4 rounded-2xl border bg-card p-5 sm:p-6">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold text-muted-foreground">Afirmación {index}</span>
          <VerdictLabel verdict={claim.verdict} />
        </div>
        <h2 className="font-quote text-xl leading-[1.55] text-pretty">
          <span className={cn("mark", verdict.mark)}>{claim.text}</span>
        </h2>
      </div>
      <p className="max-w-[72ch] text-[0.95rem] leading-relaxed">{claim.rationale}</p>
      {claim.confidence_note && (
        <p className="text-sm text-muted-foreground">{claim.confidence_note}</p>
      )}
      {claim.evidence.length > 0 ? (
        <div className="flex flex-col gap-3 border-t pt-4">
          <h3 className="text-sm font-semibold">
            {claim.evidence.length === 1
              ? "1 fuente citada"
              : `${claim.evidence.length} fuentes citadas`}
          </h3>
          <ul className="flex flex-col gap-3">
            {claim.evidence.map((evidence) => (
              <EvidenceItem key={evidence.url} evidence={evidence} />
            ))}
          </ul>
        </div>
      ) : (
        <p className="border-t pt-4 text-sm text-muted-foreground">
          Ninguna fuente de confianza publicó algo citable sobre esta afirmación.
        </p>
      )}
    </li>
  );
}

function EvidenceItem({ evidence }: { evidence: ReportEvidence }) {
  const { source } = evidence;
  const stance = STANCE_STYLES[evidence.stance];

  return (
    <li className="flex flex-col gap-3 rounded-xl bg-muted/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-semibold">{source.name}</span>
          <span className="text-sm text-muted-foreground">{source.domain}</span>
          <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", stance.className)}>
            {stance.label}
          </span>
        </div>
        <span
          className="flex items-center gap-2 text-xs text-muted-foreground"
          title={`Confiabilidad histórica basada en ${source.cases_count} casos`}
        >
          Confiabilidad
          <ScoreMeter score={source.score} className="text-foreground" />
          {source.low_sample && (
            <span
              className="rounded-full border px-2 py-0.5"
              title="Menos de 10 casos: el puntaje aún es poco estable"
            >
              Pocos casos
            </span>
          )}
        </span>
      </div>
      <blockquote className="font-quote text-[1.02rem] leading-relaxed text-foreground/85">
        “{evidence.snippet}”
      </blockquote>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <a
          href={evidence.url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="inline-flex min-w-0 items-center gap-1 font-medium text-primary underline-offset-4 hover:underline"
        >
          <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">Leer en {source.domain}</span>
        </a>
        {evidence.published_at && <span>Publicado: {evidence.published_at}</span>}
      </div>
    </li>
  );
}
