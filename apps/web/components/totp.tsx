"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";

// QR enrollment and recovery codes are shown both on first login (/login/2fa)
// and when re-enrolling from /settings/security.

export function QrEnrollment({
  qrCodeBase64,
  otpauthUri,
  onContinue,
}: {
  qrCodeBase64: string;
  otpauthUri: string | null;
  onContinue: () => void;
}) {
  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm leading-relaxed text-muted-foreground">
        Abre tu app de autenticación (Google Authenticator, Authy, 1Password…) y escanea este
        código.
      </p>
      <div className="flex justify-center rounded-xl border bg-white p-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`data:image/png;base64,${qrCodeBase64}`}
          alt="Código QR para configurar la verificación en dos pasos"
          className="size-48"
        />
      </div>
      {otpauthUri && (
        <details className="text-sm text-muted-foreground">
          <summary className="cursor-pointer font-medium text-foreground">
            ¿No puedes escanearlo? Copia el enlace
          </summary>
          <p className="mt-2 rounded-md bg-muted p-2 font-mono text-xs break-all select-all">
            {otpauthUri}
          </p>
        </details>
      )}
      <Button className="h-10 w-full" onClick={onContinue}>
        Ya lo escaneé
      </Button>
    </div>
  );
}

export function RecoveryCodes({ codes }: { codes: string[] }) {
  function download() {
    const blob = new Blob([codes.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "fakesnews-recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm leading-relaxed text-muted-foreground">
        Si pierdes el teléfono, cada código te deja entrar una vez. Guárdalos ahora: no se
        volverán a mostrar.
      </p>
      <ol className="grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-xl border border-dashed bg-muted/50 p-4 font-mono text-sm">
        {codes.map((rc) => (
          <li key={rc} className="select-all">
            {rc}
          </li>
        ))}
      </ol>
      <Button variant="outline" className="h-9" onClick={download}>
        <Download />
        Descargar códigos
      </Button>
    </div>
  );
}
