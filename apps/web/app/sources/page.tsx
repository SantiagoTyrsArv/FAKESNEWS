"use client";

import { useEffect, useState } from "react";
import { AppShell, LoadingLine, PageHeading } from "@/components/app-shell";
import { ScoreMeter } from "@/components/verdict";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { apiFetch } from "@/lib/api";
import { me } from "@/lib/auth";

interface SourceSummary {
  domain: string;
  name: string;
  type: string;
  country: string | null;
  score: number;
  cases_count: number;
  low_sample: boolean;
}

// Public page (the API's /sources is unauthenticated): visitors get the public
// header with sign-in links, signed-in users keep their session navigation.
export default function SourcesPage() {
  const [sources, setSources] = useState<SourceSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState<boolean | null>(null);

  useEffect(() => {
    me()
      .then(() => setSignedIn(true))
      .catch(() => setSignedIn(false));

    apiFetch<{ sources: SourceSummary[] }>("/sources")
      .then((res) => setSources([...res.sources].sort((a, b) => b.score - a.score)))
      .catch(() =>
        setError("No se pudo cargar el listado de fuentes. Recarga la página para reintentar."),
      );
  }, []);

  return (
    <AppShell variant={signedIn === null ? "pending" : signedIn ? "app" : "public"}>
      <PageHeading
        title="Confiabilidad de las fuentes"
        description="El puntaje mide qué tan seguido la postura de cada fuente coincidió con el consenso de las demás fuentes independientes. Mide consistencia entre fuentes, no la verdad absoluta, y se ajusta con cada caso verificado."
      />

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {sources === null && !error && <LoadingLine />}

      {sources && sources.length > 0 && (
        <div className="overflow-hidden rounded-2xl border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium sm:px-5">
                  Fuente
                </th>
                <th scope="col" className="hidden px-4 py-3 font-medium sm:table-cell">
                  Tipo
                </th>
                <th scope="col" className="hidden px-4 py-3 text-right font-medium md:table-cell">
                  Casos
                </th>
                <th scope="col" className="px-4 py-3 font-medium sm:px-5">
                  Confiabilidad
                </th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.domain} className="border-b last:border-b-0">
                  <td className="px-4 py-3.5 sm:px-5">
                    <div className="font-semibold">{source.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {source.domain}
                      {source.country ? `, ${source.country}` : ""}
                    </div>
                  </td>
                  <td className="hidden px-4 py-3.5 text-muted-foreground capitalize sm:table-cell">
                    {source.type}
                  </td>
                  <td className="hidden px-4 py-3.5 text-right tabular-nums md:table-cell">
                    {source.cases_count}
                  </td>
                  <td className="px-4 py-3.5 sm:px-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <ScoreMeter score={source.score} />
                      {source.low_sample && (
                        <span
                          className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground"
                          title="Menos de 10 casos: el puntaje aún es poco estable"
                        >
                          Pocos casos
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="max-w-[72ch] text-sm leading-relaxed text-muted-foreground">
        Cada fuente parte de un puntaje inicial según su tipo (por ejemplo, los organismos
        oficiales parten más alto que los medios). Las fuentes que se replican entre sí (por
        ejemplo, la misma agencia en dos dominios) cuentan como una sola voz, para que no inflen el
        consenso. Con menos de 10 casos el puntaje todavía es poco estable.
      </p>
    </AppShell>
  );
}
