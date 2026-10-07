import type { ReactNode } from "react";
import { SiteHeader } from "@/components/site-header";
import { cn } from "@/lib/utils";

export function AppShell({
  children,
  variant = "app",
  width = "default",
}: {
  children: ReactNode;
  variant?: "app" | "public";
  width?: "default" | "narrow";
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader variant={variant} />
      <main
        className={cn(
          "mx-auto flex w-full flex-1 flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12",
          width === "narrow" ? "max-w-2xl" : "max-w-5xl",
        )}
      >
        {children}
      </main>
    </div>
  );
}

export function PageHeading({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-balance sm:text-3xl">{title}</h1>
        {description && (
          <p className="text-[0.95rem] leading-relaxed text-pretty text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </div>
  );
}

export function LoadingLine({ children = "Cargando…" }: { children?: ReactNode }) {
  return (
    <p className="animate-pulse text-sm text-muted-foreground" role="status">
      {children}
    </p>
  );
}
