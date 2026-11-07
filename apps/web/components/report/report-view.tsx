import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ClaimCard } from "@/components/report/claim-card";
import {
  VERDICTS,
  VERDICT_ORDER,
  VerdictBar,
} from "@/components/verdict";
import {
  INPUT_TYPE_LABELS,
  type Report,
} from "@/lib/cases";
import { cn } from "@/lib/utils";

export function ReportView({ report }: Readonly<{ report: Report }>) {
  const { submission, summary, claims, disclaimer } = report;
  const counts = {
    SUPPORTED: summary.supported,
    CONTRADICTED: summary.contradicted,
    INSUFFICIENT: summary.insufficient,
  };

  return (
    <>
      <section className="animated fadeIn flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            Reporte de credibilidad ({INPUT_TYPE_LABELS[submission.input_type].toLowerCase()}),
            enviado el{" "}
            {new Date(submission.created_at).toLocaleString("es", {
              dateStyle: "long",
              timeStyle: "short",
            })}
          </p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            {claimsHeading(summary.total_claims)}
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
              {summary.failed > 0 && (
                <li className="flex items-center gap-2 text-sm">
                  <span className="font-semibold tabular-nums">{summary.failed}</span>
                  <span className="text-muted-foreground">sin verificar por un error</span>
                </li>
              )}
            </ul>
          </div>
        )}

        <p className="border-l-2 border-primary pl-4 text-sm leading-relaxed text-muted-foreground">
          {disclaimer}
        </p>
      </section>

      {claims.length === 0 ? (
        <p className="animated fadeIn rounded-2xl border border-dashed p-6 text-sm leading-relaxed text-muted-foreground">
          El contenido no tiene hechos comprobables: las opiniones y las predicciones se descartan.
        </p>
      ) : (
        <ol className="animated fadeIn flex flex-col gap-5">
          {claims.map((claim, index) => (
            <ClaimCard key={claim.id} claim={claim} index={index + 1} />
          ))}
        </ol>
      )}

      <div className="animated fadeIn flex flex-wrap gap-3 border-t pt-6">
        <Button size="md" data-magnetic="0.2" render={<Link href="/submit" />}>
          Verificar otro contenido
        </Button>
        <Button variant="outline" size="md" render={<Link href="/sources" />}>
          Cómo medimos a las fuentes
        </Button>
      </div>
    </>
  );
}

function claimsHeading(total: number): string {
  if (total === 0) return "No encontramos afirmaciones comprobables";
  if (total === 1) return "Revisamos 1 afirmación";
  return `Revisamos ${total} afirmaciones`;
}
