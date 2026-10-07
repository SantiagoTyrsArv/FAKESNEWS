import { CircleCheck, CircleHelp, CircleX, type LucideIcon } from "lucide-react";
import type { Verdict } from "@/lib/cases";
import { cn } from "@/lib/utils";

interface VerdictStyle {
  label: string;
  plural: string;
  icon: LucideIcon;
  text: string;
  tint: string;
  mark: string;
  bar: string;
}

export const VERDICTS: Record<Verdict, VerdictStyle> = {
  SUPPORTED: {
    label: "Respaldada por fuentes",
    plural: "respaldadas",
    icon: CircleCheck,
    text: "text-supported",
    tint: "bg-supported-tint",
    mark: "mark-supported",
    bar: "bg-supported",
  },
  CONTRADICTED: {
    label: "Contradicha por fuentes",
    plural: "contradichas",
    icon: CircleX,
    text: "text-contradicted",
    tint: "bg-contradicted-tint",
    mark: "mark-contradicted",
    bar: "bg-contradicted",
  },
  INSUFFICIENT: {
    label: "Evidencia insuficiente",
    plural: "sin evidencia suficiente",
    icon: CircleHelp,
    text: "text-insufficient",
    tint: "bg-insufficient-tint",
    mark: "mark-insufficient",
    bar: "bg-insufficient",
  },
};

export const VERDICT_ORDER: Verdict[] = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT"];

export function VerdictLabel({ verdict, className }: { verdict: Verdict; className?: string }) {
  const { label, icon: Icon, text } = VERDICTS[verdict];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm font-semibold", text, className)}>
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      {label}
    </span>
  );
}

// Proportional bar of how the claims in a report split across verdicts.
export function VerdictBar({ counts }: { counts: Record<Verdict, number> }) {
  const total = VERDICT_ORDER.reduce((sum, v) => sum + counts[v], 0);
  if (total === 0) return null;
  return (
    <div
      className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full"
      role="img"
      aria-label={VERDICT_ORDER.map((v) => `${counts[v]} ${VERDICTS[v].plural}`).join(", ")}
    >
      {VERDICT_ORDER.map((v) =>
        counts[v] > 0 ? (
          <span
            key={v}
            className={cn("h-full", VERDICTS[v].bar)}
            style={{ width: `${(counts[v] / total) * 100}%` }}
          />
        ) : null,
      )}
    </div>
  );
}

// Source reliability as a short meter plus the number, so it reads at a glance.
export function ScoreMeter({ score, className }: { score: number; className?: string }) {
  const pct = Math.round(score * 100);
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="relative h-1.5 w-16 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <span
          className="absolute inset-y-0 left-0 rounded-full bg-primary"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="text-sm font-semibold tabular-nums">{pct}%</span>
    </span>
  );
}
