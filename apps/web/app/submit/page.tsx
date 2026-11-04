import type { Metadata } from "next";
import { SubmitClient } from "./submit-client";

export const metadata: Metadata = {
  title: "Verificar contenido",
  description:
    "Pega un texto, un enlace o un video: separamos las afirmaciones comprobables y las contrastamos con fuentes de confianza.",
};

export default function SubmitPage() {
  return <SubmitClient />;
}
