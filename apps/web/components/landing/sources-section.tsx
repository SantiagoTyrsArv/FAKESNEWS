import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";

// Where the trust comes from: a closed list of sources, each with a track
// record, and syndicated copies counted as a single voice.
export function SourcesSection() {
  return (
    <section className="torn-top relative overflow-hidden bg-collage-blue text-white">
      <div
        aria-hidden="true"
        className="halftone pointer-events-none absolute inset-y-0 right-0 w-1/2 [--halftone-color:oklch(1_0_0/0.1)]"
      />
      <div className="relative mx-auto grid w-full max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <div className="flex flex-col gap-4">
          <p className="kicker text-white/80">Fuentes</p>
          <h2 className="font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            De dónde sale la confianza
          </h2>
          <p className="max-w-[52ch] leading-relaxed text-pretty text-white/85">
            Cada afirmación se contrasta con una lista cerrada de medios y organismos de confianza.
            De cada fuente guardamos un historial: cuántas veces su postura coincidió con la de las
            demás fuentes independientes.
          </p>
          <p className="max-w-[52ch] leading-relaxed text-pretty text-white/85">
            Si dos sitios publican la misma nota de la misma agencia, cuentan como una sola voz.
            Así nadie infla el consenso repitiendo lo mismo.
          </p>
          <div className="pt-2">
            <Button
              size="lg"
              className="h-11 bg-white px-5 text-base font-semibold text-collage-blue hover:bg-white/90"
              render={<Link href="/sources" />}
            >
              Ver la confiabilidad de las fuentes
            </Button>
          </div>
        </div>
        <div className="cutout bg-white p-2 [--cutout-rotate:1.2deg]">
          <Image
            src="/media/sources.webp"
            alt="Collage de papel: periódicos doblados y apilados como un archivo, con sellos sin texto."
            width={800}
            height={600}
            sizes="(min-width: 1024px) 440px, 100vw"
            className="h-auto w-full"
          />
        </div>
      </div>
    </section>
  );
}
