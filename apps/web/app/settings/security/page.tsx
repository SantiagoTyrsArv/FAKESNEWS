"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AppShell, LoadingLine, PageHeading } from "@/components/app-shell";
import { QrEnrollment, RecoveryCodes } from "@/components/totp";
import { confirmTotp, disableTotp, me, setupTotp, type UserResponse } from "@/lib/auth";
import { ApiError } from "@/lib/api";

type Stage = "idle" | "enroll" | "confirm" | "recovery-codes" | "disable";

export default function SecuritySettingsPage() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [stage, setStage] = useState<Stage>("idle");
  const [qrCodeBase64, setQrCodeBase64] = useState<string | null>(null);
  const [otpauthUri, setOtpauthUri] = useState<string | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
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

  function goIdle() {
    setStage("idle");
    setCode("");
    setRecoveryCode("");
    setUseRecovery(false);
    setError(null);
  }

  async function handleDisable(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const updated = await disableTotp(
        useRecovery ? { recovery_code: recoveryCode } : { code },
      );
      setUser(updated);
      goIdle();
    } catch (err) {
      setError(disableErrorMessage(err));
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
        <section className="animated fadeIn flex flex-col gap-6 rounded-2xl border bg-card p-5 sm:p-7">
          <MfaStatus enabled={user?.mfa_enabled ?? false} />

          {error && (
            <Alert variant="destructive" className="animated fadeIn">
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
              <div className="flex flex-wrap gap-2">
                <Button className="h-10 w-fit px-4" onClick={startEnrollment} disabled={loading}>
                  {enrollButtonLabel(loading, user?.mfa_enabled ?? false)}
                </Button>
                {user?.mfa_enabled && (
                  <Button
                    variant="outline"
                    className="h-10 w-fit px-4"
                    onClick={() => setStage("disable")}
                    disabled={loading}
                  >
                    Desactivar
                  </Button>
                )}
              </div>
            </div>
          )}

          {stage === "disable" && (
            <form onSubmit={handleDisable} className="flex flex-col gap-4 border-t pt-5">
              <p className="text-sm leading-relaxed text-muted-foreground">
                Para desactivarla, confirma que eres tú. Después podrás entrar solo con tu
                contraseña, y tus códigos de recuperación dejarán de funcionar.
              </p>
              <DisableCodeField
                useRecovery={useRecovery}
                code={code}
                recoveryCode={recoveryCode}
                onCodeChange={setCode}
                onRecoveryCodeChange={setRecoveryCode}
              />
              <button
                type="button"
                className="w-fit text-left text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                onClick={() => {
                  setUseRecovery((v) => !v);
                  setError(null);
                }}
              >
                {useRecovery
                  ? "Usar el código de la app"
                  : "¿No tienes el teléfono? Usa un código de recuperación"}
              </button>
              <div className="flex gap-2">
                <Button type="submit" variant="destructive" className="h-10 px-4" disabled={loading}>
                  {loading ? "Comprobando…" : "Desactivar verificación en dos pasos"}
                </Button>
                <Button type="button" variant="ghost" className="h-10" onClick={goIdle}>
                  Cancelar
                </Button>
              </div>
            </form>
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
                <Button type="button" variant="ghost" className="h-10" onClick={goIdle}>
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

function enrollButtonLabel(loading: boolean, mfaEnabled: boolean): string {
  if (loading) return "Preparando…";
  return mfaEnabled ? "Configurar en otro teléfono" : "Activar verificación en dos pasos";
}

function disableErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 429) {
    return "Demasiados intentos. Intenta de nuevo en unos minutos.";
  }
  if (err instanceof ApiError && err.status === 423) {
    return "Cuenta bloqueada temporalmente por demasiados intentos fallidos.";
  }
  return "Código inválido.";
}

// The 2FA status line: icon, title and what it means for the account.
function MfaStatus({ enabled }: Readonly<{ enabled: boolean }>) {
  const tone = enabled
    ? "bg-supported-tint text-supported"
    : "bg-insufficient-tint text-insufficient";
  return (
    <div className="flex items-start gap-4">
      <span className={`flex size-10 shrink-0 items-center justify-center rounded-full ${tone}`}>
        {enabled ? <ShieldCheck className="size-5" /> : <ShieldAlert className="size-5" />}
      </span>
      <div className="flex flex-1 flex-col gap-1">
        <h2 className="font-heading text-xl font-semibold">Verificación en dos pasos</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {enabled
            ? "Activada. Cada inicio de sesión pide un código de tu app de autenticación."
            : "Opcional y no activada. Actívala para que nadie entre solo con tu contraseña."}
        </p>
      </div>
    </div>
  );
}

// To turn 2FA off: the app's code, or a recovery code without the phone.
function DisableCodeField({
  useRecovery,
  code,
  recoveryCode,
  onCodeChange,
  onRecoveryCodeChange,
}: Readonly<{
  useRecovery: boolean;
  code: string;
  recoveryCode: string;
  onCodeChange: (value: string) => void;
  onRecoveryCodeChange: (value: string) => void;
}>) {
  if (useRecovery) {
    return (
      <div className="flex flex-col gap-2">
        <Label htmlFor="disable-recovery-code">Código de recuperación</Label>
        <Input
          id="disable-recovery-code"
          required
          autoComplete="off"
          className="h-12 max-w-72 font-mono"
          value={recoveryCode}
          onChange={(e) => onRecoveryCodeChange(e.target.value)}
        />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="disable-code">Código de la app</Label>
      <Input
        id="disable-code"
        inputMode="numeric"
        autoComplete="one-time-code"
        placeholder="123456"
        required
        className="h-12 max-w-56 text-center font-mono text-xl tracking-[0.4em]"
        value={code}
        onChange={(e) => onCodeChange(e.target.value)}
      />
    </div>
  );
}
