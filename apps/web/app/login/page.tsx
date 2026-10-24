"use client";

import { Suspense, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AuthShell } from "@/components/auth-shell";
import { useErrorBounce, type CharacterState } from "@/components/auth/characters";
import { PasswordInput } from "@/components/auth/password-input";
import { login, savePendingToken } from "@/lib/auth";
import { ApiError } from "@/lib/api";

// Only the "account created" notice reads the URL, so only it waits for the
// client (useSearchParams); the form itself is in the server HTML and shows
// even without JS.
function RegisteredNotice() {
  const searchParams = useSearchParams();
  if (searchParams.get("registered") !== "1") return null;
  return (
    <Alert>
      <AlertDescription>
        Cuenta creada. Ya puedes iniciar sesión.
      </AlertDescription>
    </Alert>
  );
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // What the characters react to.
  const [focus, setFocus] = useState<CharacterState["focus"]>("none");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [errorKey, setErrorKey] = useState(0);
  const form = useRef<HTMLFormElement>(null);
  useErrorBounce(form, errorKey);

  function fail(message: string) {
    setError(message);
    setErrorKey((k) => k + 1);
  }

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
        fail("Cuenta bloqueada temporalmente por demasiados intentos fallidos.");
      } else if (err instanceof ApiError && err.status === 429) {
        fail("Demasiados intentos. Intenta de nuevo en unos minutos.");
      } else if (err instanceof ApiError) {
        fail(err.message);
      } else {
        fail("No se pudo iniciar sesión.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Inicia sesión"
      description="Con tu correo y contraseña. Si activaste la verificación en dos pasos, después te pediremos el código de tu app."
      characters={{ focus, passwordVisible, caret: email.length, errorKey }}
    >
      <form ref={form} onSubmit={handleSubmit} className="flex flex-col gap-5">
        <Suspense fallback={null}>
          <RegisteredNotice />
        </Suspense>
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
            onFocus={() => setFocus("email")}
            onBlur={() => setFocus("none")}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Contraseña</Label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            value={password}
            onChange={setPassword}
            visible={passwordVisible}
            onVisibleChange={setPasswordVisible}
            onFocus={() => setFocus("password")}
            onBlur={() => setFocus("none")}
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
