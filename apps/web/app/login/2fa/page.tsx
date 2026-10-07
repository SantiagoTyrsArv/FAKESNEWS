"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AuthShell } from "@/components/auth-shell";
import { clearPendingToken, readPendingToken, verifyTotp } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function TwoFactorPage() {
  const router = useRouter();
  const [pendingToken, setPendingTokenState] = useState<string | null>(null);
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
    // sessionStorage (set by the login page) isn't available during server
    // rendering, so this one-time sync of external state has to happen here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPendingTokenState(pending);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      } else if (err instanceof ApiError && err.message.includes("token")) {
        setError("El inicio de sesión caducó. Vuelve a escribir tu contraseña.");
      } else {
        setError("Código inválido.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Escribe tu código"
      description="Abre tu app de autenticación y escribe los 6 dígitos de FakesNews."
      step={{ current: 2, total: 2 }}
    >
      {!pendingToken ? (
        <p className="animate-pulse text-sm text-muted-foreground" role="status">
          Preparando…
        </p>
      ) : (
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
