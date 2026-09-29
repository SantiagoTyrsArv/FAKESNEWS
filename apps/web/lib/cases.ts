import { apiFetch, csrfHeaders } from "@/lib/api";

export type InputType = "text" | "url" | "video";

export type SubmissionStatus =
  | "queued"
  | "ingesting"
  | "transcribing"
  | "extracting"
  | "verifying"
  | "scoring"
  | "done"
  | "failed";

export type Verdict = "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT";

export type Stance = "supports" | "contradicts" | "neutral";

export interface Submission {
  id: string;
  input_type: InputType;
  raw_input: string;
  status: SubmissionStatus;
  error: string | null;
  created_at: string;
}

export interface ReportSource {
  domain: string;
  name: string;
  type: string;
  score: number;
  cases_count: number;
  low_sample: boolean;
}

export interface ReportEvidence {
  url: string;
  snippet: string;
  published_at: string | null;
  stance: Stance;
  source: ReportSource;
}

export interface ReportClaim {
  id: string;
  text: string;
  verdict: Verdict;
  rationale: string;
  confidence_note: string | null;
  evidence: ReportEvidence[];
}

export interface Report {
  submission: Omit<Submission, "error">;
  summary: {
    total_claims: number;
    supported: number;
    contradicted: number;
    insufficient: number;
  };
  claims: ReportClaim[];
  disclaimer: string;
}

export const TERMINAL_STATUSES: SubmissionStatus[] = ["done", "failed"];

export const STATUS_LABELS: Record<SubmissionStatus, string> = {
  queued: "En cola",
  ingesting: "Obteniendo contenido",
  transcribing: "Transcribiendo video",
  extracting: "Extrayendo afirmaciones",
  verifying: "Verificando con fuentes",
  scoring: "Actualizando reputación de fuentes",
  done: "Listo",
  failed: "Falló",
};

export const INPUT_TYPE_LABELS: Record<InputType, string> = {
  text: "Texto",
  url: "URL",
  video: "Video",
};

export function createSubmission(inputType: InputType, rawInput: string) {
  return apiFetch<Submission>("/submissions", {
    method: "POST",
    headers: csrfHeaders(),
    body: JSON.stringify({ input_type: inputType, raw_input: rawInput }),
  });
}

export function getSubmission(id: string) {
  return apiFetch<Submission>(`/submissions/${encodeURIComponent(id)}`);
}

export function listSubmissions() {
  return apiFetch<{ submissions: Submission[] }>("/submissions");
}

export function getReport(id: string) {
  return apiFetch<Report>(`/reports/${encodeURIComponent(id)}`);
}
