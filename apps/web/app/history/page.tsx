"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/site-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import {
  INPUT_TYPE_LABELS,
  listSubmissions,
  STATUS_LABELS,
  type Submission,
} from "@/lib/cases";

export default function HistoryPage() {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<Submission[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSubmissions()
      .then((res) => setSubmissions(res.submissions))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login");
        } else {
          setError("No se pudo cargar el historial.");
        }
      });
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-black">
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-10">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle>Historial de casos</CardTitle>
                <CardDescription>Tus verificaciones, de la más reciente a la más antigua.</CardDescription>
              </div>
              <Button render={<Link href="/submit" />}>Nuevo caso</Button>
            </div>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            {submissions === null && !error && (
              <p className="text-sm text-muted-foreground">Cargando...</p>
            )}
            {submissions?.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Todavía no enviaste ningún caso.
              </p>
            )}
            {submissions && submissions.length > 0 && (
              <ul className="divide-y">
                {submissions.map((s) => (
                  <li key={s.id}>
                    <Link
                      href={`/reports/${s.id}`}
                      className="flex flex-wrap items-center justify-between gap-2 py-3 hover:bg-muted/40"
                    >
                      <span className="flex min-w-0 flex-1 flex-col gap-1">
                        <span className="truncate text-sm">{s.raw_input}</span>
                        <span className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Badge variant="outline">{INPUT_TYPE_LABELS[s.input_type]}</Badge>
                          {new Date(s.created_at).toLocaleString("es")}
                        </span>
                      </span>
                      <Badge
                        variant={
                          s.status === "done"
                            ? "default"
                            : s.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {STATUS_LABELS[s.status]}
                      </Badge>
                    </Link>
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
