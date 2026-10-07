"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Wordmark } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/submit", label: "Verificar" },
  { href: "/history", label: "Mis casos" },
  { href: "/sources", label: "Fuentes" },
  { href: "/settings/security", label: "Seguridad" },
];

export type HeaderVariant = "app" | "public" | "pending";

// `variant="public"` is for visitors on pages anyone can open (like /sources):
// it offers sign-in instead of the session navigation and logout. "pending"
// shows only the wordmark while such a page is still checking the session,
// so a signed-in user never sees a flash of the sign-in buttons.
export function SiteHeader({ variant = "app" }: { variant?: HeaderVariant }) {
  const router = useRouter();
  const pathname = usePathname();

  async function handleLogout() {
    try {
      await logout();
    } finally {
      router.push("/login");
    }
  }

  return (
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center gap-4 px-4 sm:gap-6 sm:px-6">
        <Wordmark compact={variant !== "public"} />
        {variant === "app" ? (
          <>
            <nav
              aria-label="Principal"
              className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              {LINKS.map((link) => {
                const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "shrink-0 rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
                      active && "bg-accent text-accent-foreground hover:text-accent-foreground",
                    )}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              aria-label="Cerrar sesión"
              className="shrink-0"
            >
              <LogOut />
              <span className="hidden sm:inline">Cerrar sesión</span>
            </Button>
          </>
        ) : variant === "public" ? (
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="sm" render={<Link href="/login" />}>
              Iniciar sesión
            </Button>
            <Button size="sm" render={<Link href="/register" />}>
              Crear cuenta
            </Button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
