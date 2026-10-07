"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Link as LinkIcon, Video, type LucideIcon } from "lucide-react";
import { AppShell, PageHeading } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ApiError } from "@/lib/api";
import { createSubmission, type InputType } from "@/lib/cases";
import { cn } from "@/lib/utils";

const MAX_LENGTH = 10000;

const INPUT_TYPES: { value: InputType; label: string; hint: string; icon: LucideIcon }[] = [
  {
    value: "text",
    label: "Texto",
    hint: "Un mensaje de WhatsApp, una publicación o un fragmento de noticia.",
    icon: FileText,
  },
  {
    value: "url",
    label: "Enlace a un artículo",
    hint: "Extraemos el texto principal de la página.",
    icon: LinkIcon,
  },
  {
    value: "video",
    label: "Video",
    hint: "YouTube, TikTok, Vimeo o Dailymotion. Transcribimos el audio; los videos de más de 10 minutos se rechazan.",
    icon: Video,
  },
];

export default function SubmitPage() {
  const router = useRouter();
  const [inputType, setInputType] = useState<InputType>("text");
  const [rawInput, setRawInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const current = INPUT_TYPES.find((t) => t.value === inputType)!;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const submission = await createSubmission(inputType, rawInput.trim());
      router.push(`/reports/${submission.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login");
        return;
      }
      setError(err instanceof ApiError ? err.message : "No se pudo enviar el caso.");
      setLoading(false);
    }
  }

  return (
    <AppShell width="narrow">
      <PageHeading
        title="¿Qué quieres verificar?"
        description="Separamos el contenido en afirmaciones comprobables y buscamos cada una en fuentes de confianza. El resultado es un reporte con citas."
      />

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-3 text-sm font-medium">Tipo de contenido</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {INPUT_TYPES.map(({ value, label, icon: Icon }) => (
              <label
                key={value}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-xl border bg-card px-4 py-3 text-sm font-medium transition-colors has-focus-visible:ring-3 has-focus-visible:ring-ring/50",
                  inputType === value
                    ? "border-primary bg-accent text-accent-foreground"
                    : "hover:border-foreground/25",
                )}
              >
                <input
                  type="radio"
                  name="input-type"
                  value={value}
                  checked={inputType === value}
                  onChange={() => {
                    setInputType(value);
                    setRawInput("");
                  }}
                  className="sr-only"
                />
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                {label}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-col gap-2">
          <Label htmlFor="raw-input">{inputType === "text" ? "Contenido" : "Enlace"}</Label>
          {inputType === "text" ? (
            <Textarea
              id="raw-input"
              required
              rows={10}
              maxLength={MAX_LENGTH}
              placeholder="Pega aquí el texto que te llegó…"
              className="min-h-52 bg-card text-[0.95rem] leading-relaxed"
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
            />
          ) : (
            <Input
              id="raw-input"
              type="url"
              required
              placeholder="https://"
              maxLength={MAX_LENGTH}
              className="h-11 bg-card"
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
            />
          )}
          <div className="flex justify-between gap-4 text-xs text-muted-foreground">
            <p>{current.hint}</p>
            {inputType === "text" && (
              <p className="shrink-0 tabular-nums">
                {rawInput.length.toLocaleString("es")} / {MAX_LENGTH.toLocaleString("es")}
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 border-t pt-6">
          <Button
            type="submit"
            disabled={loading || !rawInput.trim()}
            className="h-11 px-6 text-[0.95rem]"
          >
            {loading ? "Enviando…" : "Verificar"}
          </Button>
          <p className="text-sm text-muted-foreground">Suele tardar entre uno y tres minutos.</p>
        </div>
      </form>
    </AppShell>
  );
}
