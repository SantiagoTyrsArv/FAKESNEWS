"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { AppShell, LoadingLine } from "@/components/app-shell";
import { PipelineProgress } from "@/components/report/pipeline-progress";
import { ReportView } from "@/components/report/report-view";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  getReport,
  getSubmission,
  TERMINAL_STATUSES,
  type Report,
  type Submission,
} from "@/lib/cases";

const POLL_INTERVAL_MS = 2000;
// A bit over the worker's job timeout (PIPELINE_JOB_TIMEOUT_SECONDS, 15 min):
// past it the case should already be done or failed, so stop polling instead
// of spinning forever. Measured from created_at, so a reload doesn't reset it.
const STALE_AFTER_MS = 16 * 60 * 1000;

export function ReportClient({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    // Done: load the report. Still running: poll again, unless it has been
    // running for too long. Failed: nothing more to do.
    async function onStatus(current: Submission) {
      if (current.status === "done") {
        const fullReport = await getReport(id);
        if (!cancelled) setReport(fullReport);
        return;
      }
      if (TERMINAL_STATUSES.includes(current.status)) return;
      if (Date.now() - new Date(current.created_at).getTime() > STALE_AFTER_MS) {
        setStale(true);
        return;
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    function onError(err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login");
      } else if (err instanceof ApiError && err.status === 404) {
        setError("No existe un caso con este enlace en tu cuenta.");
      } else {
        setError("No se pudo cargar el caso. Reintentando…");
        timer = setTimeout(poll, POLL_INTERVAL_MS * 2);
      }
    }

    async function poll() {
      try {
        const current = await getSubmission(id);
        if (cancelled) return;
        setSubmission(current);
        await onStatus(current);
      } catch (err) {
        if (!cancelled) onError(err);
      }
    }

    // poll handles its own errors, so the returned promise never rejects.
    void poll();
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
        <Alert variant="destructive" className="animated fadeIn">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!submission && !error && <LoadingLine />}

      {submission && !report && submission.status !== "failed" && !stale && (
        <PipelineProgress submission={submission} />
      )}

      {stale && submission?.status !== "failed" && !report && (
        <section className="animated fadeIn flex flex-col items-start gap-4 rounded-2xl border bg-card p-6 sm:p-8">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Este análisis está tardando demasiado</h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Lleva más tiempo del esperado sin terminar. Recarga la página en unos minutos o envía el
            caso de nuevo.
          </p>
          <Button size="md" data-magnetic="0.2" render={<Link href="/submit" />}>
            Enviar otro caso
          </Button>
        </section>
      )}

      {submission?.status === "failed" && (
        <section className="animated fadeIn flex flex-col items-start gap-4 rounded-2xl border bg-card p-6 sm:p-8">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">No pudimos terminar este análisis</h1>
          <Alert variant="destructive">
            <AlertDescription>
              {submission.error ?? "Error desconocido en el procesamiento."}
            </AlertDescription>
          </Alert>
          <p className="text-sm text-muted-foreground">
            Si enviaste un enlace, comprueba que sea público o prueba pegando el texto directamente.
          </p>
          <Button size="md" data-magnetic="0.2" render={<Link href="/submit" />}>
            Enviar otro caso
          </Button>
        </section>
      )}

      {report && <ReportView report={report} />}
    </AppShell>
  );
}
