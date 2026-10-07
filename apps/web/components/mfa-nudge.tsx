"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ShieldAlert, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { me } from "@/lib/auth";

const DISMISS_KEY = "fakesnews_mfa_nudge_dismissed";

function readDismissed(): boolean {
  try {
    return sessionStorage.getItem(DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

// 2FA is optional, so accounts without it can be opened with the password
// alone. This keeps reminding those users (once per browser session) where to
// turn it on, without blocking anything.
export function MfaNudge() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (readDismissed()) return;
    let cancelled = false;
    me()
      .then((user) => {
        if (!cancelled && !user.mfa_enabled) setShow(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!show) return null;

  function dismiss() {
    setShow(false);
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // Storage unavailable: the reminder simply comes back on the next page.
    }
  }

  return (
    <Alert className="pr-10">
      <ShieldAlert aria-hidden="true" />
      <AlertTitle>Tu cuenta no tiene verificación en dos pasos</AlertTitle>
      <AlertDescription>
        Hoy basta tu contraseña para entrar. Actívala en{" "}
        <Link href="/settings/security" className="font-medium underline underline-offset-4">
          Seguridad
        </Link>{" "}
        para pedir también un código de tu app de autenticación.
      </AlertDescription>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Ocultar aviso"
        className="absolute top-2 right-2 rounded-md p-1 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </Alert>
  );
}
