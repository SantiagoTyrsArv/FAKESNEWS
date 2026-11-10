import type { Metadata } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";
import { serverFetch } from "@/lib/server-api";
import { type SourceSummary, SourcesClient } from "./sources-client";

export const metadata: Metadata = {
  title: "Confiabilidad de las fuentes",
  description:
    "Qué tan seguido la postura de cada fuente coincidió con el consenso de las demás fuentes independientes, caso a caso.",
};

// Requirement: rendering patterns — ISR. The page is prerendered and served
// from the cache; at most once every 60 s a request triggers a regeneration in
// the background. 60 s matches the API's own `Cache-Control: public,
// max-age=60` for /sources (apps/api/app/core/middleware.py:62).
export const revalidate = 60;

async function loadSources(): Promise<SourceSummary[] | null> {
  try {
    const { sources } = await serverFetch<{ sources: SourceSummary[] }>("/sources", {
      next: { revalidate },
    });
    return [...sources].sort((a, b) => b.score - a.score);
  } catch (error) {
    // At build time the API may be down (it scales to zero): ship the page
    // without data and let the browser fetch it, as before. In a
    // regeneration, throw instead, so Next keeps serving the last good page.
    if (process.env.NEXT_PHASE === PHASE_PRODUCTION_BUILD) return null;
    throw error;
  }
}

export default async function SourcesPage() {
  return <SourcesClient initialSources={await loadSources()} />;
}
