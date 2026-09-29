"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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

  function downloadRecoveryCodes() {
    const blob = new Blob([recoveryCodes.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "fakesnews-recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loadingUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
        <p className="text-sm text-muted-foreground">Cargando...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Seguridad de la cuenta</CardTitle>
          <CardDescription>{user?.email}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex items-center justify-between rounded-md border p-3">
            <span className="text-sm">Verificación en dos pasos (TOTP)</span>
            <Badge variant={user?.mfa_enabled ? "default" : "secondary"}>
              {user?.mfa_enabled ? "Activada" : "No activada"}
            </Badge>
          </div>

          {stage === "idle" && (
            <Button onClick={startEnrollment} disabled={loading}>
              {user?.mfa_enabled ? "Reenrolar dispositivo 2FA" : "Activar 2FA"}
            </Button>
          )}

          {stage === "enroll" && qrCodeBase64 && (
            <div className="flex flex-col items-center gap-4">
              <p className="text-sm text-muted-foreground">
                Escanea este código con tu aplicación de autenticación.
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
            </div>
          )}

          {stage === "confirm" && (
            <form onSubmit={handleConfirm} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="confirm-code">Código de 6 dígitos</Label>
                <Input
                  id="confirm-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              <Button type="submit" disabled={loading}>
                {loading ? "Verificando..." : "Confirmar"}
              </Button>
            </form>
          )}

          {stage === "recovery-codes" && (
            <div className="flex flex-col gap-4">
              <Alert>
                <AlertDescription>
                  Nuevos códigos de recuperación generados. Los anteriores ya no son
                  válidos. Guárdalos ahora: no se mostrarán de nuevo.
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
              <Button onClick={() => setStage("idle")}>Listo</Button>
            </div>
          )}
        </CardContent>
        <CardFooter>
          <p className="text-xs text-muted-foreground">
            Reenrolar reemplaza tu dispositivo TOTP actual y todos tus códigos de
            recuperación anteriores.
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
