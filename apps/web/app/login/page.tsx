"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AuthShell } from "@/components/auth-shell";
import { login, savePendingToken } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const justRegistered = searchParams.get("registered") === "1";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await login(email, password);
      if (res.status === "authenticated") {
        router.push("/history");
      } else {
        savePendingToken(res.token);
        router.push("/login/2fa");
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) {
        setError("Cuenta bloqueada temporalmente por demasiados intentos fallidos.");
      } else if (err instanceof ApiError && err.status === 429) {
        setError("Demasiados intentos. Intenta de nuevo en unos minutos.");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No se pudo iniciar sesión.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Inicia sesión"
      description="Con tu correo y contraseña. Si activaste la verificación en dos pasos, después te pediremos el código de tu app."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {justRegistered && (
          <Alert>
            <AlertDescription>
              Cuenta creada. Ya puedes iniciar sesión.
            </AlertDescription>
          </Alert>
        )}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Correo electrónico</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            className="h-10"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Contraseña</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            className="h-10"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={loading} className="h-10 w-full">
          {loading ? "Comprobando…" : "Continuar"}
        </Button>
        <p className="text-sm text-muted-foreground">
          ¿No tienes cuenta?{" "}
          <Link href="/register" className="font-medium text-primary underline-offset-4 hover:underline">
            Crea una
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
