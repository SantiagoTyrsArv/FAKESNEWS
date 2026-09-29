"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";

const LINKS = [
  { href: "/submit", label: "Verificar" },
  { href: "/history", label: "Historial" },
  { href: "/sources", label: "Fuentes" },
  { href: "/settings/security", label: "Seguridad" },
];

export function SiteHeader() {
  const router = useRouter();

  async function handleLogout() {
    try {
      await logout();
    } finally {
      router.push("/login");
    }
  }

  return (
    <header className="border-b bg-background">
      <nav className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3">
        <Link href="/" className="font-semibold">
          FakesNews
        </Link>
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            {link.label}
          </Link>
        ))}
        <Button variant="ghost" size="sm" className="ml-auto" onClick={handleLogout}>
          Cerrar sesión
        </Button>
      </nav>
    </header>
  );
}
