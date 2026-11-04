import type { Metadata } from "next";
import { SourcesClient } from "./sources-client";

export const metadata: Metadata = {
  title: "Confiabilidad de las fuentes",
  description:
    "Qué tan seguido la postura de cada fuente coincidió con el consenso de las demás fuentes independientes, caso a caso.",
};

export default function SourcesPage() {
  return <SourcesClient />;
}
