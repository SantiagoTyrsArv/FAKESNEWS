import type { Metadata } from "next";
import { ReportClient } from "./report-client";

export const metadata: Metadata = {
  title: "Reporte de verificación",
  description: "Qué respalda y qué contradice cada fuente de confianza, afirmación por afirmación.",
};

export default async function ReportPage({ params }: PageProps<"/reports/[id]">) {
  const { id } = await params;
  return <ReportClient id={id} />;
}
