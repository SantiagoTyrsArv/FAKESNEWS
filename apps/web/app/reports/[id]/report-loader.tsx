import { cookies } from "next/headers";
import { loadInitialCase } from "@/lib/server-api";
import { ReportClient } from "./report-client";

// Requirement: rendering patterns — SSR with streaming. This async Server
// Component reads the session cookie and the case on the server while the
// page's <Suspense> fallback is already on screen; its HTML arrives later in
// the same response. If the server can't load the case, ReportClient gets no
// initial data and fetches it in the browser, as before (CSR fallback).
export async function ReportLoader({ params }: Readonly<{ params: Promise<{ id: string }> }>) {
  const { id } = await params;
  const accessToken = (await cookies()).get("access_token")?.value;
  const initial = await loadInitialCase(id, accessToken);
  return (
    <ReportClient
      id={id}
      initialSubmission={initial?.submission ?? null}
      initialReport={initial?.report ?? null}
    />
  );
}
