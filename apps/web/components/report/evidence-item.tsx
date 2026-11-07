import { ExternalLink } from "lucide-react";
import { ScoreMeter } from "@/components/verdict";
import type { ReportEvidence, Stance } from "@/lib/cases";
import { formatPublishedDate } from "@/lib/format-date.mjs";
import { evidenceUrl } from "@/lib/source-url.mjs";
import { cn } from "@/lib/utils";

const STANCE_STYLES: Record<Stance, { label: string; className: string }> = {
  supports: { label: "Respalda", className: "bg-supported-tint text-supported" },
  contradicts: { label: "Contradice", className: "bg-contradicted-tint text-contradicted" },
  neutral: { label: "Neutral", className: "bg-muted text-muted-foreground" },
};

export function EvidenceItem({
  evidence,
  onTimeline = false,
}: Readonly<{ evidence: ReportEvidence; onTimeline?: boolean }>) {
  const { source } = evidence;
  const stance = STANCE_STYLES[evidence.stance];
  const href = evidenceUrl(evidence.url);

  return (
    <li
      data-testid={onTimeline ? "timeline-item" : undefined}
      className="relative flex flex-col gap-3 rounded-xl bg-muted/50 p-4"
    >
      {onTimeline && (
        <span
          aria-hidden="true"
          className="absolute top-5 -left-[1.4rem] size-2.5 rounded-full bg-changed"
        />
      )}
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
              className="rounded-full border px-2 py-0.5 text-foreground/70"
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
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="inline-flex min-w-0 items-center gap-1 font-medium text-primary underline-offset-4 hover:underline"
          >
            <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">Leer en {source.domain}</span>
          </a>
        )}
        {evidence.published_at && (
          <span>Publicado: {formatPublishedDate(evidence.published_at)}</span>
        )}
      </div>
    </li>
  );
}
