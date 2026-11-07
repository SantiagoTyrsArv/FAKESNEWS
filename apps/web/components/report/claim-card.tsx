import { FailedLabel, VERDICTS, VerdictLabel } from "@/components/verdict";
import { EvidenceItem } from "@/components/report/evidence-item";
import { EvidenceTimeline } from "@/components/report/evidence-timeline";
import type { ReportClaim } from "@/lib/cases";
import { cn } from "@/lib/utils";

export function ClaimCard({ claim, index }: Readonly<{ claim: ReportClaim; index: number }>) {
  const verdict = VERDICTS[claim.verdict];

  return (
    <li className="flex flex-col gap-4 rounded-2xl border bg-card p-5 sm:p-6">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold text-muted-foreground">Afirmación {index}</span>
          {claim.verification_failed ? <FailedLabel /> : <VerdictLabel verdict={claim.verdict} />}
        </div>
        <h2 className="font-quote text-xl leading-[1.55] text-pretty">
          <span className={cn(!claim.verification_failed && "mark", !claim.verification_failed && verdict.mark)}>
            {claim.text}
          </span>
        </h2>
      </div>
      <p className="max-w-[72ch] text-[0.95rem] leading-relaxed">{claim.rationale}</p>
      {claim.confidence_note && (
        <p className="text-sm text-muted-foreground">{claim.confidence_note}</p>
      )}
      <ClaimEvidence claim={claim} />
    </p>
      )}
    </li>
  );
}

function ClaimEvidence({ claim }: Readonly<{ claim: ReportClaim }>) {
  if (claim.evidence.length === 0) {
    return (
      <p className="border-t pt-4 text-sm text-muted-foreground">
        {claim.verification_failed
          ? "No fue posible consultar las fuentes. Envía el caso de nuevo más tarde."
          : "Ninguna fuente de confianza publicó algo citable sobre esta afirmación."}
      </p>
    );
  }
  if (claim.verdict === "CHANGED" && !claim.verification_failed) {
    return <EvidenceTimeline evidence={claim.evidence} />;
  }
  return (
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
  );
}
