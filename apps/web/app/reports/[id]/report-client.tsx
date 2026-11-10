"use client";

import { useEffect, useRef, useState } from "react";
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
import { watchSubmission } from "@/lib/submission-socket";

const POLL_INTERVAL_MS = 2000;
// A bit over the worker's job timeout (PIPELINE_JOB_TIMEOUT_SECONDS, 15 min):
// past it the case should already be done or failed, so stop polling instead
// of spinning forever. Measured from created_at, so a reload doesn't reset it.
const STALE_AFTER_MS = 16 * 60 * 1000;

function isStale(submission: Submission) {
  return Date.now() - new Date(submission.created_at).getTime() > STALE_AFTER_MS;
}

// initialSubmission/initialReport come from the server render when it could
// read the case (SSR, see page.tsx); otherwise the page loads it here (CSR).
export function ReportClient({
  id,
  initialSubmission = null,
  initialReport = null,
}: Readonly<{ id: string; initialSubmission?: Submission | null; initialReport?: Report | null }>) {
  const router = useRouter();
  const [submission, setSubmission] = useState<Submission | null>(initialSubmission);
  const [report, setReport] = useState<Report | null>(initialReport);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  // Only the first render's server data seeds the effect; later props don't
  // restart it.
  const initial = useRef({ submission: initialSubmission, report: initialReport });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopSocket: (() => void) | undefined;

    async function loadReport() {
      const fullReport = await getReport(id);
      if (!cancelled) setReport(fullReport);
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

    // Fallback: polling, as before the WebSocket. Done: load the report.
    // Still running: poll again, unless it has been running for too long.
    // Failed: nothing more to do.
    async function onPolledStatus(current: Submission) {
      if (current.status === "done") {
        await loadReport();
        return;
      }
      if (TERMINAL_STATUSES.includes(current.status)) return;
      if (isStale(current)) {
        setStale(true);
        return;
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    async function poll() {
      try {
        const current = await getSubmission(id);
        if (cancelled) return;
        setSubmission(current);
        await onPolledStatus(current);
      } catch (err) {
        if (!cancelled) onError(err);
      }
    }

    // Requirement: WebSockets. Follow the case live; any trouble with the
    // socket hands over to poll() (lib/submission-socket.ts).
    function follow(current: Submission) {
      if (current.status === "done") {
        if (!initial.current.report) loadReport().catch((err) => !cancelled && onError(err));
        return;
      }
      if (TERMINAL_STATUSES.includes(current.status)) return;
      if (isStale(current)) {
        setStale(true);
        return;
      }
      stopSocket = watchSubmission(id, {
        onStatus: (event) => {
          if (cancelled) return;
          setSubmission((prev) => prev && { ...prev, ...event });
          setError(null);
          if (event.status === "done") loadReport().catch((err) => !cancelled && onError(err));
        },
        onFallback: () => {
          if (!cancelled) void poll();
        },
      });
    }

    async function start() {
      try {
        const current = initial.current.submission ?? (await getSubmission(id));
        if (cancelled) return;
        setSubmission(current);
        follow(current);
      } catch (err) {
        if (!cancelled) onError(err);
      }
    }

    // start handles its own errors, so the returned promise never rejects.
    void start();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      stopSocket?.();
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
