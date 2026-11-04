import type { Metadata } from "next";
import { HistoryClient } from "./history-client";

export const metadata: Metadata = {
  title: "Mis casos",
  description: "Todo lo que enviaste a verificar, del más reciente al más antiguo.",
};

export default function HistoryPage() {
  return <HistoryClient />;
}
