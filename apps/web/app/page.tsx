"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { logout, me, type UserResponse } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecked(true));
  }, []);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      setUser(null);
      router.refresh();
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle className="text-2xl">FakesNews</CardTitle>
          <CardDescription>
            Verificación asistida por IA de noticias sospechosas, con trazabilidad
            de fuentes.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Esta plataforma nunca declara una noticia &ldquo;verdadera&rdquo; o
            &ldquo;falsa&rdquo;. Entrega un reporte de credibilidad trazable:
            afirmaciones verificadas, fuentes concretas y el historial de
            confiabilidad de cada fuente.
          </p>

          {!checked ? null : user ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-muted-foreground">
                Sesión iniciada como {user.email}
              </span>
              <Button render={<Link href="/submit" />}>Verificar contenido</Button>
              <Button render={<Link href="/history" />} variant="outline">
                Historial
              </Button>
              <Button render={<Link href="/settings/security" />} variant="outline">
                Ajustes de seguridad
              </Button>
              <Button variant="ghost" onClick={handleLogout}>
                Cerrar sesión
              </Button>
            </div>
          ) : (
            <div className="flex gap-3">
              <Button render={<Link href="/register" />}>Crear cuenta</Button>
              <Button variant="outline" render={<Link href="/login" />}>
                Iniciar sesión
              </Button>
              <Button variant="ghost" render={<Link href="/sources" />}>
                Ver fuentes
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
