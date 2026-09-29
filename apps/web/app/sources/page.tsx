"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

interface SourceSummary {
  domain: string;
  name: string;
  type: string;
  country: string | null;
  score: number;
  cases_count: number;
  low_sample: boolean;
}

// Public page (the API's /sources is unauthenticated), so it uses a minimal
// header instead of SiteHeader, whose links and logout assume a session.
export default function SourcesPage() {
  const [sources, setSources] = useState<SourceSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ sources: SourceSummary[] }>("/sources")
      .then((res) => setSources([...res.sources].sort((a, b) => b.score - a.score)))
      .catch(() => setError("No se pudo cargar el listado de fuentes."));
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-black">
      <header className="border-b bg-background">
        <nav className="mx-auto flex max-w-4xl items-center gap-4 px-6 py-3">
          <Link href="/" className="font-semibold">
            FakesNews
          </Link>
        </nav>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-10">
        <Card>
          <CardHeader>
            <CardTitle>Confiabilidad de fuentes</CardTitle>
            <CardDescription>
              Puntaje = qué tan seguido la postura de cada fuente coincidió con el
              consenso ponderado de fuentes independientes. Mide consistencia entre
              fuentes, no verdad objetiva. Ver <code>docs/reputation.md</code> para la
              fórmula y sus limitaciones.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            {sources === null && !error && (
              <p className="text-sm text-muted-foreground">Cargando...</p>
            )}
            {sources && (
              <ul className="divide-y">
                {sources.map((source) => (
                  <li
                    key={source.domain}
                    className="flex flex-wrap items-center justify-between gap-2 py-3"
                  >
                    <span className="flex flex-col">
                      <span className="text-sm font-medium">{source.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {source.domain} · {source.type}
                        {source.country ? ` · ${source.country}` : ""}
                      </span>
                    </span>
                    <span className="flex items-center gap-2">
                      {source.low_sample && (
                        <Badge variant="outline" title="Menos de 10 casos">
                          Muestra pequeña
                        </Badge>
                      )}
                      <Badge variant="secondary">
                        {Math.round(source.score * 100)}% · {source.cases_count} casos
                      </Badge>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
