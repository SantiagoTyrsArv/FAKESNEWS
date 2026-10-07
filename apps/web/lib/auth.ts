import { apiFetch, csrfHeaders } from "@/lib/api";

export interface RegisterResponse {
  id: string;
  email: string;
}

// Without 2FA the password alone opens the session (cookies are set);
// with 2FA it returns a short-lived token for /2fa/verify.
export type LoginResponse =
  | { status: "authenticated"; user: UserResponse }
  | { status: "mfa_required"; token: string; token_type: "mfa_pending"; expires_in: number };

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

export function savePendingToken(token: string) {
  sessionStorage.setItem(PENDING_TOKEN_KEY, token);
}

export function readPendingToken(): string | null {
  return sessionStorage.getItem(PENDING_TOKEN_KEY);
}

export function clearPendingToken() {
  sessionStorage.removeItem(PENDING_TOKEN_KEY);
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
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// Enrolling and disabling 2FA happen from settings, with a full session.
export function setupTotp() {
  return apiFetch<TotpSetupResponse>("/auth/2fa/setup", {
    method: "POST",
    headers: csrfHeaders(),
  });
}

export function confirmTotp(code: string) {
  return apiFetch<TotpConfirmResponse>("/auth/2fa/confirm", {
    method: "POST",
    headers: csrfHeaders(),
    body: JSON.stringify({ code }),
  });
}

export function disableTotp(body: { code?: string; recovery_code?: string }) {
  return apiFetch<UserResponse>("/auth/2fa/disable", {
    method: "POST",
    headers: csrfHeaders(),
    body: JSON.stringify(body),
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
