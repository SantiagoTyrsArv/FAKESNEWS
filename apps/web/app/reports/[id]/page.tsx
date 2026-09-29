"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/site-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  type Verdict,
} from "@/lib/cases";

const POLL_INTERVAL_MS = 2000;

const PIPELINE_STEPS: SubmissionStatus[] = [
  "queued",
  "ingesting",
  "transcribing",
  "extracting",
  "verifying",
  "scoring",
  "done",
];

const VERDICT_STYLES: Record<Verdict, { label: string; className: string }> = {
  SUPPORTED: {
    label: "Respaldada por fuentes",
    className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  },
  CONTRADICTED: {
    label: "Contradicha por fuentes",
    className: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
  },
  INSUFFICIENT: {
    label: "Evidencia insuficiente",
    className: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
  },
};

const STANCE_LABELS: Record<Stance, string> = {
  supports: "Respalda",
  contradicts: "Contradice",
  neutral: "Neutral",
};

function progressFor(status: SubmissionStatus): number {
  const index = PIPELINE_STEPS.indexOf(status);
  return index < 0 ? 0 : Math.round((index / (PIPELINE_STEPS.length - 1)) * 100);
}

export default function ReportPage({ params }: PageProps<"/reports/[id]">) {
  const { id } = use(params);
  const router = useRouter();
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login");
        } else if (err instanceof ApiError && err.status === 404) {
          setError("Caso no encontrado.");
        } else {
          setError("No se pudo cargar el caso. Reintentando...");
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
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-black">
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-10">
        {error && !report && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!submission && !error && (
          <p className="text-sm text-muted-foreground">Cargando...</p>
        )}

        {submission && !report && submission.status !== "failed" && (
          <Card>
            <CardHeader>
              <CardTitle>Analizando el contenido</CardTitle>
              <CardDescription>
                {STATUS_LABELS[submission.status]}. Esta página se actualiza sola.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Progress value={progressFor(submission.status)} />
            </CardContent>
          </Card>
        )}

        {submission?.status === "failed" && (
          <Card>
            <CardHeader>
              <CardTitle>No se pudo completar el análisis</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Alert variant="destructive">
                <AlertDescription>
                  {submission.error ?? "Error desconocido en el procesamiento."}
                </AlertDescription>
              </Alert>
              <Button className="w-fit" render={<Link href="/submit" />}>
                Enviar otro caso
              </Button>
            </CardContent>
          </Card>
        )}

        {report && <ReportView report={report} />}
      </main>
    </div>
  );
}

function ReportView({ report }: { report: Report }) {
  const { submission, summary, claims, disclaimer } = report;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Reporte de credibilidad</CardTitle>
          <CardDescription>
            {INPUT_TYPE_LABELS[submission.input_type]} ·{" "}
            {new Date(submission.created_at).toLocaleString("es")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="line-clamp-4 whitespace-pre-wrap break-words rounded-md border bg-muted/40 p-3 text-sm">
            {submission.raw_input}
          </p>
          <div className="flex flex-wrap gap-2 text-sm">
            <Badge variant="outline">{summary.total_claims} afirmaciones</Badge>
            <Badge className={VERDICT_STYLES.SUPPORTED.className}>
              {summary.supported} respaldadas
            </Badge>
            <Badge className={VERDICT_STYLES.CONTRADICTED.className}>
              {summary.contradicted} contradichas
            </Badge>
            <Badge className={VERDICT_STYLES.INSUFFICIENT.className}>
              {summary.insufficient} sin evidencia suficiente
            </Badge>
          </div>
          <Alert>
            <AlertDescription>{disclaimer}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {claims.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No se encontraron afirmaciones factuales verificables en este contenido
          (opiniones y predicciones se descartan).
        </p>
      ) : (
        claims.map((claim, index) => (
          <ClaimCard key={claim.id} claim={claim} index={index + 1} />
        ))
      )}
    </>
  );
}

function ClaimCard({ claim, index }: { claim: ReportClaim; index: number }) {
  const verdict = VERDICT_STYLES[claim.verdict];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-base">
            {index}. {claim.text}
          </CardTitle>
          <Badge className={verdict.className}>{verdict.label}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm">{claim.rationale}</p>
        {claim.confidence_note && (
          <p className="text-xs text-muted-foreground">{claim.confidence_note}</p>
        )}
        {claim.evidence.length > 0 ? (
          <ul className="flex flex-col gap-3">
            {claim.evidence.map((evidence) => (
              <EvidenceItem key={evidence.url} evidence={evidence} />
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">
            Sin evidencia citable de fuentes de confianza.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function EvidenceItem({ evidence }: { evidence: ReportEvidence }) {
  const { source } = evidence;

  return (
    <li className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{source.name}</span>
        <span className="text-muted-foreground">{source.domain}</span>
        <Badge variant="outline">{STANCE_LABELS[evidence.stance]}</Badge>
        <Badge
          variant="secondary"
          title={`Confiabilidad histórica basada en ${source.cases_count} casos`}
        >
          Confiabilidad {Math.round(source.score * 100)}%
        </Badge>
        {source.low_sample && (
          <Badge variant="outline" title="Menos de 10 casos: el puntaje es poco estable">
            Muestra pequeña
          </Badge>
        )}
      </div>
      <blockquote className="border-l-2 pl-3 text-sm text-muted-foreground">
        {evidence.snippet}
      </blockquote>
      <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
        <a
          href={evidence.url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="break-all underline"
        >
          {evidence.url}
        </a>
        {evidence.published_at && <span>Publicado: {evidence.published_at}</span>}
      </div>
    </li>
  );
}
