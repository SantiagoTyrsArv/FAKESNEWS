import { EvidenceItem } from "@/components/report/evidence-item";
import type { ReportEvidence } from "@/lib/cases";
import { orderEvidence } from "@/lib/evidence-timeline.mjs";

// Oldest first, so the reader sees what was said and what came after it.
export function EvidenceTimeline({ evidence }: Readonly<{ evidence: ReportEvidence[] }>) {
  const { dated, undated } = orderEvidence(evidence);

  return (
    <div className="flex flex-col gap-3 border-t pt-4">
      <h3 className="text-sm font-semibold">Línea de tiempo</h3>
      {dated.length > 0 && (
        <ol className="flex flex-col gap-3 border-l-2 border-changed/30 pl-4">
          {dated.map((item) => (
            <EvidenceItem key={item.url} evidence={item} onTimeline />
          ))}
        </ol>
      )}
      {undated.length > 0 && (
        <>
          <h4 className="text-sm font-semibold text-muted-foreground">Sin fecha</h4>
          <ul className="flex flex-col gap-3">
            {undated.map((item) => (
              <EvidenceItem key={item.url} evidence={item} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
