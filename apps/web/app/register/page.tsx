"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AuthShell } from "@/components/auth-shell";
import { useErrorBounce, type CharacterState } from "@/components/auth/characters";
import { PasswordInput } from "@/components/auth/password-input";
import { register } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [violations, setViolations] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  // What the characters react to; either password field counts as "password".
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
    setViolations([]);

    if (password !== confirmPassword) {
      fail("Las contraseñas no coinciden.");
      return;
    }

    setLoading(true);
    try {
      await register(email, password);
      router.push("/login?registered=1");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400 && err.body && typeof err.body === "object") {
        const detail = (err.body as { detail?: { violations?: string[] } }).detail;
        if (detail?.violations) {
          setViolations(detail.violations);
          setErrorKey((k) => k + 1);
        } else {
          fail(err.message);
        }
      } else if (err instanceof ApiError) {
        fail(err.message);
      } else {
        fail("No se pudo completar el registro.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Crea tu cuenta"
      description="Después podrás activar la verificación en dos pasos desde Ajustes de seguridad."
      characters={{ focus, passwordVisible, caret: email.length, errorKey }}
      // With every password rule listed, the strip would push "Crear cuenta"
      // below a 375×667 screen (measured: 681 px), so on phones it is left out.
      mobileCharacters={false}
    >
      <form ref={form} onSubmit={handleSubmit} className="flex flex-col gap-5">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {violations.length > 0 && (
          <Alert variant="destructive">
            <AlertDescription>
              <p className="mb-1 font-medium">La contraseña necesita:</p>
              <ul className="list-disc pl-4">
                {violations.map((v) => (
                  <li key={v}>{v}</li>
                ))}
              </ul>
            </AlertDescription>
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
            autoComplete="new-password"
            value={password}
            onChange={setPassword}
            visible={passwordVisible}
            onVisibleChange={setPasswordVisible}
            onFocus={() => setFocus("password")}
            onBlur={() => setFocus("none")}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="confirm-password">Repite la contraseña</Label>
          <PasswordInput
            id="confirm-password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={setConfirmPassword}
            visible={passwordVisible}
            onVisibleChange={setPasswordVisible}
            onFocus={() => setFocus("password")}
            onBlur={() => setFocus("none")}
          />
        </div>
        <Button type="submit" disabled={loading} className="h-10 w-full">
          {loading ? "Creando cuenta…" : "Crear cuenta"}
        </Button>
        <p className="text-sm text-muted-foreground">
          ¿Ya tienes cuenta?{" "}
          <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Inicia sesión
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
