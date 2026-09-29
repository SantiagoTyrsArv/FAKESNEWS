import { apiFetch, csrfHeaders } from "@/lib/api";

export interface RegisterResponse {
  id: string;
  email: string;
}

export interface PendingTokenResponse {
  token: string;
  token_type: "mfa_setup_pending" | "mfa_pending";
  expires_in: number;
}

export interface TotpSetupResponse {
  otpauth_uri: string;
  qr_code_base64: string;
}

export interface TotpConfirmResponse {
  recovery_codes: string[];
}

export interface UserResponse {
  id: string;
  email: string;
  mfa_enabled: boolean;
}

export interface SessionResponse {
  user: UserResponse;
}

const PENDING_TOKEN_KEY = "fakesnews_pending_token";
const PENDING_TOKEN_TYPE_KEY = "fakesnews_pending_token_type";

export function savePendingToken(token: string, tokenType: string) {
  sessionStorage.setItem(PENDING_TOKEN_KEY, token);
  sessionStorage.setItem(PENDING_TOKEN_TYPE_KEY, tokenType);
}

export function readPendingToken(): { token: string; tokenType: string } | null {
  const token = sessionStorage.getItem(PENDING_TOKEN_KEY);
  const tokenType = sessionStorage.getItem(PENDING_TOKEN_TYPE_KEY);
  if (!token || !tokenType) return null;
  return { token, tokenType };
}

export function clearPendingToken() {
  sessionStorage.removeItem(PENDING_TOKEN_KEY);
  sessionStorage.removeItem(PENDING_TOKEN_TYPE_KEY);
}

function bearer(token?: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function register(email: string, password: string) {
  return apiFetch<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string) {
  return apiFetch<PendingTokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function setupTotp(pendingToken?: string) {
  return apiFetch<TotpSetupResponse>("/auth/2fa/setup", {
    method: "POST",
    headers: bearer(pendingToken),
  });
}

export function confirmTotp(code: string, pendingToken?: string) {
  return apiFetch<TotpConfirmResponse>("/auth/2fa/confirm", {
    method: "POST",
    headers: bearer(pendingToken),
    body: JSON.stringify({ code }),
  });
}

export function verifyTotp(
  pendingToken: string,
  body: { code?: string; recovery_code?: string },
) {
  return apiFetch<SessionResponse>("/auth/2fa/verify", {
    method: "POST",
    headers: bearer(pendingToken),
    body: JSON.stringify(body),
  });
}

export function logout() {
  return apiFetch<void>("/auth/logout", {
    method: "POST",
    headers: csrfHeaders(),
  });
}

export function me() {
  return apiFetch<UserResponse>("/auth/me");
}
