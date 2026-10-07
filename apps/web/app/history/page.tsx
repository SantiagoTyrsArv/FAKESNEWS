"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileText, Link as LinkIcon, Plus, Video } from "lucide-react";
import { MfaNudge } from "@/components/mfa-nudge";
import { AppShell, LoadingLine, PageHeading } from "@/components/app-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  INPUT_TYPE_LABELS,
  listSubmissions,
  STATUS_LABELS,
  type InputType,
  type Submission,
  type SubmissionStatus,
} from "@/lib/cases";
import { cn } from "@/lib/utils";

const TYPE_ICONS: Record<InputType, typeof FileText> = {
  text: FileText,
  url: LinkIcon,
  video: Video,
};

function StatusPill({ status }: { status: SubmissionStatus }) {
  const done = status === "done";
  const failed = status === "failed";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        done && "bg-accent text-accent-foreground",
        failed && "bg-contradicted-tint text-contradicted",
        !done && !failed && "bg-muted text-muted-foreground",
      )}
    >
      {!done && !failed && (
        <span className="size-1.5 animate-pulse rounded-full bg-primary" aria-hidden="true" />
      )}
      {done ? "Reporte listo" : STATUS_LABELS[status]}
    </span>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<Submission[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSubmissions()
      .then((res) => setSubmissions(res.submissions))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login");
        } else {
          setError("No se pudo cargar tu historial. Recarga la página para intentarlo de nuevo.");
        }
      });
  }, [router]);

  return (
    <AppShell>
      <MfaNudge />

      <PageHeading
        title="Mis casos"
        description="Todo lo que enviaste a verificar, del más reciente al más antiguo."
        actions={
          <Button className="h-10 px-4" render={<Link href="/submit" />}>
            <Plus />
            Nuevo caso
          </Button>
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {submissions === null && !error && <LoadingLine />}

      {submissions?.length === 0 && (
        <div className="flex flex-col items-start gap-4 rounded-2xl border border-dashed p-8 sm:p-10">
          <h2 className="text-lg font-semibold">Todavía no verificaste nada</h2>
          <p className="max-w-[52ch] text-sm leading-relaxed text-muted-foreground">
            Pega un mensaje sospechoso, el enlace a un artículo o un video. El reporte aparecerá
            aquí cuando esté listo.
          </p>
          <Button className="h-10 px-4" render={<Link href="/submit" />}>
            Verificar mi primer contenido
          </Button>
        </div>
      )}

      {submissions && submissions.length > 0 && (
        <ul className="flex flex-col overflow-hidden rounded-2xl border bg-card">
          {submissions.map((s) => {
            const Icon = TYPE_ICONS[s.input_type];
            return (
              <li key={s.id} className="border-b last:border-b-0">
                <Link
                  href={`/reports/${s.id}`}
                  className="flex items-center gap-4 px-4 py-4 transition-colors outline-none hover:bg-muted/60 focus-visible:bg-muted/60 sm:px-5"
                >
                  <span
                    className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"
                    title={INPUT_TYPE_LABELS[s.input_type]}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate text-sm font-medium">{s.raw_input}</span>
                    <time dateTime={s.created_at} className="text-xs text-muted-foreground">
                      {new Date(s.created_at).toLocaleString("es", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </time>
                  </span>
                  <StatusPill status={s.status} />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </AppShell>
  );
}
