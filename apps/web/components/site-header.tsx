"use client";

import { useLayoutEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Wordmark } from "@/components/brand";
import { useMotion } from "@/components/motion/motion-provider";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";
import { onceInSession } from "@/lib/motion/env.mjs";
import { gsap } from "@/lib/motion/gsap";
import { DURATION, EASE, scaled } from "@/lib/motion/tokens.mjs";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/submit", label: "Verificar" },
  { href: "/history", label: "Mis casos" },
  { href: "/sources", label: "Fuentes" },
  { href: "/settings/security", label: "Seguridad" },
];

const HEADER_DROP = 20;
// Never fully transparent: whether the header animates is only known after
// hydration (a once-per-session flag), so it can't be pre-hidden by CSS.
const HEADER_FROM_OPACITY = 0.6;

export type HeaderVariant = "app" | "public" | "pending";

// `variant="public"` is for visitors on pages anyone can open (like /sources):
// it offers sign-in instead of the session navigation and logout. "pending"
// shows only the wordmark while such a page is still checking the session,
// so a signed-in user never sees a flash of the sign-in buttons.
export function SiteHeader({ variant = "app" }: { variant?: HeaderVariant }) {
  const router = useRouter();
  const pathname = usePathname();
  const { reduced, intensity, ready } = useMotion();
  const ref = useRef<HTMLElement>(null);
  // Decided once per mount (a ref survives StrictMode's double effect): the
  // header drops in the first time it shows in the session, then stays put.
  const drops = useRef<boolean | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!ready || reduced || !el) return;
    drops.current ??= onceInSession("fn-header", () => sessionStorage);
    if (!drops.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { y: scaled(-HEADER_DROP, intensity), opacity: HEADER_FROM_OPACITY },
        { y: 0, opacity: 1, duration: DURATION.enter * 0.7, ease: EASE.out, clearProps: "transform,opacity" },
      );
    }, el);
    return () => ctx.revert();
  }, [ready, reduced, intensity]);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      router.push("/login");
    }
  }

  return (
    <header ref={ref} className="rule-double sticky top-0 z-30 bg-background/80 backdrop-blur">
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
