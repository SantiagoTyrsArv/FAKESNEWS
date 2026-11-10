import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell, LoadingLine } from "@/components/app-shell";
import { ReportLoader } from "./report-loader";

export const metadata: Metadata = {
  title: "Reporte de verificación",
  description: "Qué respalda y qué contradice cada fuente de confianza, afirmación por afirmación.",
};

// Requirement: rendering patterns — SSR with streaming. The page itself awaits
// nothing: the header and the fallback go out in the first chunk, and
// ReportLoader streams in once the API answers.
export default function ReportPage({ params }: PageProps<"/reports/[id]">) {
  return (
    <Suspense fallback={<ReportFallback />}>
      <ReportLoader params={params} />
    </Suspense>
  );
}

// Same loading state the client shows while it fetches the case.
function ReportFallback() {
  return (
    <AppShell>
      <LoadingLine />
    </AppShell>
  );
}
