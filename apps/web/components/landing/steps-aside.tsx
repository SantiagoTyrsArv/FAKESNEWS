import { VerdictLabel } from "@/components/verdict";

// A real result (report of 2026-11-07), so the steps next to it have proof
// beside them. The quote is verbatim from the cited article.
const EXAMPLE = {
  claim: "Ueno Bank cerró.",
  quote:
    "El Banco Central del Paraguay (BCP) intervino y cerró Ueno bank, una de las entidades más populares del país…",
  source: "El Tiempo",
  domain: "eltiempo.com",
  sources: 7,
};

const FACTS = [
  { value: "25", label: "fuentes de confianza entre medios, verificadores y organismos" },
  { value: "4", label: "afirmaciones como máximo por caso, solo hechos comprobables" },
  { value: "100 %", label: "de las citas salen de la página de la fuente, ninguna la escribe la IA" },
];

// Only on large screens: there the steps are taller than the section's intro,
// and on small ones the columns stack and leave no gap to fill.
export function StepsAside() {
  return (
    <div className="mt-6 hidden flex-1 flex-col justify-between gap-10 lg:flex">
      <figure
        data-reveal
        className="cutout flex flex-col gap-4 rounded-lg border bg-paper p-6"
        style={{ "--cutout-rotate": "-1deg" } as React.CSSProperties}
      >
        <figcaption className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
          <span className="font-semibold text-foreground">Un resultado real</span>
          <span>{EXAMPLE.sources} fuentes citadas</span>
        </figcaption>
        <p className="font-quote text-xl leading-relaxed text-pretty">
          <span className="mark mark-supported">{EXAMPLE.claim}</span>
        </p>
        <VerdictLabel verdict="SUPPORTED" />
        <blockquote className="border-t pt-4 font-quote leading-relaxed text-foreground/85 text-pretty">
          “{EXAMPLE.quote}”
        </blockquote>
        <p className="text-sm text-muted-foreground">
          <span className="font-semibold text-foreground">{EXAMPLE.source}</span> · {EXAMPLE.domain}
        </p>
      </figure>

      <dl data-reveal className="flex flex-col gap-4">
        {FACTS.map((fact) => (
          <div key={fact.value} className="grid grid-cols-[5rem_1fr] items-baseline gap-4">
            <dt className="font-heading text-2xl font-semibold tracking-tight">{fact.value}</dt>
            <dd className="text-sm leading-relaxed text-pretty text-muted-foreground">{fact.label}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
