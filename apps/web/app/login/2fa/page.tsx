"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AuthShell } from "@/components/auth-shell";
import { QrEnrollment, RecoveryCodes } from "@/components/totp";
import {
  clearPendingToken,
  confirmTotp,
  readPendingToken,
  setupTotp,
  verifyTotp,
} from "@/lib/auth";
import { ApiError } from "@/lib/api";

type Stage = "loading" | "enroll" | "confirm" | "recovery-codes" | "verify" | "error";

export default function TwoFactorPage() {
  const router = useRouter();
  const [pendingToken, setPendingTokenState] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("loading");
  const [qrCodeBase64, setQrCodeBase64] = useState<string | null>(null);
  const [otpauthUri, setOtpauthUri] = useState<string | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const pending = readPendingToken();
    if (!pending) {
      router.replace("/login");
      return;
    }
    // Reading sessionStorage (set by the previous page) has to happen in an
    // effect since it isn't available during server rendering; both of
    // these setState calls are the one-time sync of that external state
    // into React, not derived state that could be computed during render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPendingTokenState(pending.token);

    if (pending.tokenType === "mfa_setup_pending") {
      setupTotp(pending.token)
        .then((res) => {
          setQrCodeBase64(res.qr_code_base64);
          setOtpauthUri(res.otpauth_uri);
          setStage("enroll");
        })
        .catch(() => setStage("error"));
    } else {
      setStage("verify");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingToken) return;
    setError(null);
    setLoading(true);
    try {
      const res = await confirmTotp(code, pendingToken);
      setRecoveryCodes(res.recovery_codes);
      setCode("");
      setStage("recovery-codes");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Código inválido.");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingToken) return;
    setError(null);
    setLoading(true);
    try {
      await verifyTotp(
        pendingToken,
        useRecovery ? { recovery_code: recoveryCode } : { code },
      );
      clearPendingToken();
      router.push("/history");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Demasiados intentos. Intenta de nuevo en unos minutos.");
      } else if (err instanceof ApiError && err.status === 423) {
        setError("Cuenta bloqueada temporalmente por demasiados intentos fallidos.");
      } else {
        setError("Código inválido.");
      }
    } finally {
      setLoading(false);
    }
  }

  const titles: Record<Stage, { title: string; description?: string }> = {
    loading: { title: "Verificación en dos pasos" },
    error: { title: "No se pudo continuar" },
    enroll: {
      title: "Activa la verificación en dos pasos",
      description: "Es obligatoria: protege tus casos aunque alguien conozca tu contraseña.",
    },
    confirm: {
      title: "Confirma el código",
      description: "Escribe los 6 dígitos que muestra tu app ahora mismo.",
    },
    "recovery-codes": { title: "Guarda tus códigos de recuperación" },
    verify: {
      title: "Escribe tu código",
      description: "Abre tu app de autenticación y escribe los 6 dígitos de FakesNews.",
    },
  };

  return (
    <AuthShell
      title={titles[stage].title}
      description={titles[stage].description}
      step={{ current: 2, total: 2 }}
    >
      {stage === "loading" && (
        <p className="animate-pulse text-sm text-muted-foreground" role="status">
          Preparando…
        </p>
      )}

      {stage === "error" && (
        <div className="flex flex-col gap-4">
          <Alert variant="destructive">
            <AlertDescription>
              El enlace de inicio de sesión caducó o no es válido. Vuelve a iniciar sesión.
            </AlertDescription>
          </Alert>
          <Button className="h-10" onClick={() => router.replace("/login")}>
            Volver a iniciar sesión
          </Button>
        </div>
      )}

      {stage === "enroll" && qrCodeBase64 && (
        <QrEnrollment
          qrCodeBase64={qrCodeBase64}
          otpauthUri={otpauthUri}
          onContinue={() => setStage("confirm")}
        />
      )}

      {stage === "confirm" && (
        <form onSubmit={handleConfirm} className="flex flex-col gap-5">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm-code">Código</Label>
            <Input
              id="confirm-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              required
              className="h-12 text-center font-mono text-xl tracking-[0.4em]"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={loading} className="h-10 w-full">
            {loading ? "Comprobando…" : "Confirmar"}
          </Button>
          <button
            type="button"
            className="text-left text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            onClick={() => setStage("enroll")}
          >
            Volver al código QR
          </button>
        </form>
      )}

      {stage === "recovery-codes" && (
        <div className="flex flex-col gap-5">
          <RecoveryCodes codes={recoveryCodes} />
          <Button className="h-10 w-full" onClick={() => setStage("verify")}>
            Ya los guardé
          </Button>
        </div>
      )}

      {stage === "verify" && (
        <form onSubmit={handleVerify} className="flex flex-col gap-5">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {!useRecovery ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor="verify-code">Código de la app</Label>
              <Input
                id="verify-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                required
                className="h-12 text-center font-mono text-xl tracking-[0.4em]"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <Label htmlFor="recovery-code">Código de recuperación</Label>
              <Input
                id="recovery-code"
                required
                autoComplete="off"
                className="h-12 font-mono"
                value={recoveryCode}
                onChange={(e) => setRecoveryCode(e.target.value)}
              />
            </div>
          )}
          <Button type="submit" disabled={loading} className="h-10 w-full">
            {loading ? "Comprobando…" : "Entrar"}
          </Button>
          <button
            type="button"
            className="text-left text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            onClick={() => {
              setUseRecovery((v) => !v);
              setError(null);
            }}
          >
            {useRecovery
              ? "Usar el código de la app"
              : "¿No tienes el teléfono? Usa un código de recuperación"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
