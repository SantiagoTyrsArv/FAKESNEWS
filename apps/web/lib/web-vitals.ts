// Requirement: INP. Turns Next's useReportWebVitals metrics (INP, LCP, CLS,
// FCP, TTFB) into the small payload POST /vitals accepts, and sends it so it
// survives the page being hidden or closed. The API writes each one to the
// log (apps/api/app/modules/vitals/routers.py).
import { apiUrl } from "@/lib/api";

export interface VitalPayload {
  name: string;
  value: number;
  rating: string;
  id: string;
  navigation_type: string | null;
  route: string;
}

export const REPORTED_METRICS = new Set(["CLS", "FCP", "INP", "LCP", "TTFB"]);

const UUID_SEGMENT = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// /reports/<uuid> -> /reports/[id]: the logs get the route, never a case id.
export function routeTemplate(pathname: string): string {
  const path = pathname.split(/[?#]/, 1)[0] || "/";
  return path
    .split("/")
    .map((segment) => (UUID_SEGMENT.test(segment) ? "[id]" : segment))
    .join("/");
}

export function toVitalPayload(
  metric: { name: string; value: number; rating: string; id: string; navigationType?: string },
  pathname: string,
): VitalPayload {
  return {
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    id: metric.id,
    navigation_type: metric.navigationType ?? null,
    route: routeTemplate(pathname),
  };
}

export function sendVital(payload: VitalPayload): void {
  const url = apiUrl("/vitals");
  const body = JSON.stringify(payload);
  try {
    // text/plain: sendBeacon can't preflight, and the API reads the raw body.
    if (navigator.sendBeacon?.(url, new Blob([body], { type: "text/plain" }))) return;
    fetch(url, {
      method: "POST",
      body,
      keepalive: true,
      credentials: "include",
      headers: { "Content-Type": "text/plain" },
    }).catch(() => {});
  } catch {
    // Metrics are best effort: never break the page over them.
  }
}
