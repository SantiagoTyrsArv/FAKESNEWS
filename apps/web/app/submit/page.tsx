"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { createSubmission, type InputType } from "@/lib/cases";

const MAX_LENGTH = 10000;

const HINTS: Record<InputType, string> = {
  text: "Pega el texto de la noticia o del mensaje que quieres verificar.",
  url: "Enlace a un artículo. Se extrae el texto principal de la página.",
  video:
    "Enlace a un video de una plataforma conocida (YouTube, TikTok, etc.). Se transcribe el audio; los videos largos se rechazan.",
};

export default function SubmitPage() {
  const router = useRouter();
  const [inputType, setInputType] = useState<InputType>("text");
  const [rawInput, setRawInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-black">
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-2xl flex-col px-6 py-10">
        <Card>
          <CardHeader>
            <CardTitle>Verificar un contenido</CardTitle>
            <CardDescription>
              Extraemos las afirmaciones verificables y las contrastamos con fuentes
              de confianza. El resultado es un reporte con citas, no un veredicto de
              &ldquo;verdadero&rdquo; o &ldquo;falso&rdquo;.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleSubmit}>
            <CardContent className="flex flex-col gap-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <Tabs
                value={inputType}
                onValueChange={(value) => {
                  setInputType(value as InputType);
                  setRawInput("");
                }}
              >
                <TabsList>
                  <TabsTrigger value="text">Texto</TabsTrigger>
                  <TabsTrigger value="url">URL</TabsTrigger>
                  <TabsTrigger value="video">Video</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="flex flex-col gap-2">
                <Label htmlFor="raw-input">
                  {inputType === "text" ? "Contenido" : "Enlace"}
                </Label>
                {inputType === "text" ? (
                  <Textarea
                    id="raw-input"
                    required
                    rows={8}
                    maxLength={MAX_LENGTH}
                    value={rawInput}
                    onChange={(e) => setRawInput(e.target.value)}
                  />
                ) : (
                  <Input
                    id="raw-input"
                    type="url"
                    required
                    placeholder="https://..."
                    maxLength={MAX_LENGTH}
                    value={rawInput}
                    onChange={(e) => setRawInput(e.target.value)}
                  />
                )}
                <p className="text-xs text-muted-foreground">{HINTS[inputType]}</p>
              </div>
            </CardContent>
            <CardFooter className="mt-4">
              <Button type="submit" disabled={loading || !rawInput.trim()}>
                {loading ? "Enviando..." : "Verificar"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </main>
    </div>
  );
}
