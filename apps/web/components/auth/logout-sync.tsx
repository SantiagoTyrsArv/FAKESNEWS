"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { onLogoutElsewhere } from "@/lib/auth-channel";

// Pages anyone can open. The login flow includes /login/2fa.
const PUBLIC_PATHS = new Set(["/", "/login", "/register", "/sources"]);

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.has(pathname) || pathname.startsWith("/login/");
}

// Requirement: postMessage. Mounted once in the root layout, it listens on the
// BroadcastChannel for a logout made in another tab. A private page goes to
// /login; a public one reloads, because the header reads the session once and
// would keep showing the signed-in navigation.
export function LogoutSync(): null {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(
    () =>
      onLogoutElsewhere(() => {
        if (isPublic(pathname)) window.location.reload();
        else router.replace("/login");
      }),
    [pathname, router],
  );

  return null;
}
