import { VERDICTS, VerdictLabel } from "@/components/verdict";
import { EvidenceItem } from "@/components/report/evidence-item";
import type { ReportClaim } from "@/lib/cases";
import { cn } from "@/lib/utils";

export function ClaimCard({ claim, index }: Readonly<{ claim: ReportClaim; index: number }>) {
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
