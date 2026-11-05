import type { Metadata } from "next";
import { SecurityClient } from "./security-client";

export const metadata: Metadata = {
  title: "Seguridad de la cuenta",
  description: "Activa o gestiona la verificación en dos pasos de tu cuenta.",
};

export default function SecuritySettingsPage() {
  return <SecurityClient />;
}
