"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AppShell, LoadingLine, PageHeading } from "@/components/app-shell";
import { QrEnrollment, RecoveryCodes } from "@/components/totp";
import { confirmTotp, me, setupTotp, type UserResponse } from "@/lib/auth";
import { ApiError } from "@/lib/api";

type Stage = "idle" | "enroll" | "confirm" | "recovery-codes";

export default function SecuritySettingsPage() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [stage, setStage] = useState<Stage>("idle");
  const [qrCodeBase64, setQrCodeBase64] = useState<string | null>(null);
  const [otpauthUri, setOtpauthUri] = useState<string | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoadingUser(false));
  }, []);

  async function startEnrollment() {
    setError(null);
    setLoading(true);
    try {
      const res = await setupTotp();
      setQrCodeBase64(res.qr_code_base64);
      setOtpauthUri(res.otpauth_uri);
      setStage("enroll");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar el enrolamiento.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await confirmTotp(code);
      setRecoveryCodes(res.recovery_codes);
      setCode("");
      setStage("recovery-codes");
      const refreshed = await me();
      setUser(refreshed);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Código inválido.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell width="narrow">
      <PageHeading
        title="Seguridad de la cuenta"
        description={loadingUser ? undefined : user?.email}
      />

      {loadingUser ? (
        <LoadingLine />
      ) : (
        <section className="flex flex-col gap-6 rounded-2xl border bg-card p-5 sm:p-7">
          <div className="flex items-start gap-4">
            <span
              className={
                user?.mfa_enabled
                  ? "flex size-10 shrink-0 items-center justify-center rounded-full bg-supported-tint text-supported"
                  : "flex size-10 shrink-0 items-center justify-center rounded-full bg-insufficient-tint text-insufficient"
              }
            >
              {user?.mfa_enabled ? <ShieldCheck className="size-5" /> : <ShieldAlert className="size-5" />}
            </span>
            <div className="flex flex-1 flex-col gap-1">
              <h2 className="font-semibold">Verificación en dos pasos</h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {user?.mfa_enabled
                  ? "Activada. Cada inicio de sesión pide un código de tu app de autenticación."
                  : "No activada. Actívala para que nadie entre solo con tu contraseña."}
              </p>
            </div>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {stage === "idle" && (
            <div className="flex flex-col gap-3 border-t pt-5">
              <p className="text-sm leading-relaxed text-muted-foreground">
                {user?.mfa_enabled
                  ? "¿Cambiaste de teléfono? Configura la app de nuevo. El dispositivo anterior y todos tus códigos de recuperación dejarán de funcionar."
                  : "Necesitarás una app como Google Authenticator, Authy o 1Password."}
              </p>
              <Button className="h-10 w-fit px-4" onClick={startEnrollment} disabled={loading}>
                {loading
                  ? "Preparando…"
                  : user?.mfa_enabled
                    ? "Configurar en otro teléfono"
                    : "Activar verificación en dos pasos"}
              </Button>
            </div>
          )}

          {stage === "enroll" && qrCodeBase64 && (
            <div className="border-t pt-5">
              <QrEnrollment
                qrCodeBase64={qrCodeBase64}
                otpauthUri={otpauthUri}
                onContinue={() => setStage("confirm")}
              />
            </div>
          )}

          {stage === "confirm" && (
            <form onSubmit={handleConfirm} className="flex flex-col gap-4 border-t pt-5">
              <div className="flex flex-col gap-2">
                <Label htmlFor="confirm-code">Código de 6 dígitos</Label>
                <Input
                  id="confirm-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="123456"
                  required
                  className="h-12 max-w-56 text-center font-mono text-xl tracking-[0.4em]"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" className="h-10 px-4" disabled={loading}>
                  {loading ? "Comprobando…" : "Confirmar"}
                </Button>
                <Button type="button" variant="ghost" className="h-10" onClick={() => setStage("idle")}>
                  Cancelar
                </Button>
              </div>
            </form>
          )}

          {stage === "recovery-codes" && (
            <div className="flex flex-col gap-4 border-t pt-5">
              <h3 className="font-semibold">Tus nuevos códigos de recuperación</h3>
              <RecoveryCodes codes={recoveryCodes} />
              <Button className="h-10 w-fit px-4" onClick={() => setStage("idle")}>
                Ya los guardé
              </Button>
            </div>
          )}
        </section>
      )}
    </AppShell>
  );
}
