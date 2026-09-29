"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

  function downloadRecoveryCodes() {
    const blob = new Blob([recoveryCodes.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "fakesnews-recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Verificación en dos pasos</CardTitle>
          <CardDescription>Paso 2 de 2.</CardDescription>
        </CardHeader>

        {stage === "loading" && (
          <CardContent>
            <p className="text-sm text-muted-foreground">Cargando...</p>
          </CardContent>
        )}

        {stage === "error" && (
          <CardContent>
            <Alert variant="destructive">
              <AlertDescription>
                No se pudo iniciar el enrolamiento. Vuelve a iniciar sesión.
              </AlertDescription>
            </Alert>
          </CardContent>
        )}

        {stage === "enroll" && qrCodeBase64 && (
          <CardContent className="flex flex-col items-center gap-4">
            <p className="text-sm text-muted-foreground">
              Escanea este código QR con tu aplicación de autenticación (Google
              Authenticator, Authy, etc.).
            </p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`data:image/png;base64,${qrCodeBase64}`}
              alt="Código QR para configurar 2FA"
              className="h-48 w-48"
            />
            {otpauthUri && (
              <p className="break-all text-center text-xs text-muted-foreground">
                {otpauthUri}
              </p>
            )}
            <Button className="w-full" onClick={() => setStage("confirm")}>
              Ya escaneé el código
            </Button>
          </CardContent>
        )}

        {stage === "confirm" && (
          <form onSubmit={handleConfirm}>
            <CardContent className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Ingresa el código de 6 dígitos que muestra tu aplicación.
              </p>
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
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Verificando..." : "Confirmar"}
              </Button>
            </CardFooter>
          </form>
        )}

        {stage === "recovery-codes" && (
          <>
            <CardContent className="flex flex-col gap-4">
              <Alert>
                <AlertDescription>
                  Guarda estos códigos de recuperación en un lugar seguro. Cada uno solo
                  se puede usar una vez y no se volverán a mostrar.
                </AlertDescription>
              </Alert>
              <div className="grid grid-cols-2 gap-2 rounded-md border p-3 font-mono text-sm">
                {recoveryCodes.map((rc) => (
                  <span key={rc}>{rc}</span>
                ))}
              </div>
              <Button variant="outline" onClick={downloadRecoveryCodes}>
                Descargar códigos
              </Button>
              <Separator />
              <p className="text-sm text-muted-foreground">
                Ahora ingresa un código de tu aplicación para completar el inicio de
                sesión.
              </p>
            </CardContent>
            <CardFooter>
              <Button className="w-full" onClick={() => setStage("verify")}>
                Continuar
              </Button>
            </CardFooter>
          </>
        )}

        {stage === "verify" && (
          <form onSubmit={handleVerify}>
            <CardContent className="flex flex-col gap-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              {!useRecovery ? (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="verify-code">Código de autenticación</Label>
                  <Input
                    id="verify-code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    required
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
                    value={recoveryCode}
                    onChange={(e) => setRecoveryCode(e.target.value)}
                  />
                </div>
              )}
              <button
                type="button"
                className="text-left text-sm text-muted-foreground underline"
                onClick={() => setUseRecovery((v) => !v)}
              >
                {useRecovery
                  ? "Usar código de la aplicación en su lugar"
                  : "Usar un código de recuperación en su lugar"}
              </button>
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Verificando..." : "Iniciar sesión"}
              </Button>
            </CardFooter>
          </form>
        )}
      </Card>
    </div>
  );
}
