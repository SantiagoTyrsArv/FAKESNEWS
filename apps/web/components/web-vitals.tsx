"use client";

import { useReportWebVitals } from "next/web-vitals";
import { REPORTED_METRICS, sendVital, toVitalPayload } from "@/lib/web-vitals";

// Requirement: INP. Next's built-in useReportWebVitals (no extra dependency)
// reports INP next to LCP and CLS; each one goes to the API's POST /vitals
// and from there to the logs. Module-level so the callback reference never
// changes: a new one would make Next report the same metrics again.
function report(metric: Parameters<Parameters<typeof useReportWebVitals>[0]>[0]) {
  if (!REPORTED_METRICS.has(metric.name)) return;
  sendVital(toVitalPayload(metric, window.location.pathname));
}

export function WebVitals() {
  useReportWebVitals(report);
  return null;
}
