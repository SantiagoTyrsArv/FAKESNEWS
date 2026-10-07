import Link from "next/link";
import { cn } from "@/lib/utils";

// The mark is a magnifier over a highlighted line: what the product does.
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn("size-7 shrink-0", className)}>
      <rect x="2" y="13" width="17" height="7" rx="1.5" fill="var(--insufficient-tint)" />
      <rect x="2" y="7" width="12" height="2.5" rx="1.25" fill="currentColor" opacity="0.35" />
      <rect x="2" y="15.25" width="14" height="2.5" rx="1.25" fill="currentColor" />
      <rect x="2" y="23.5" width="9" height="2.5" rx="1.25" fill="currentColor" opacity="0.35" />
      <circle cx="20" cy="16.5" r="6" fill="none" stroke="var(--primary)" strokeWidth="2.5" />
      <path d="m24.5 21 4.5 4.5" stroke="var(--primary)" strokeWidth="2.75" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({
  className,
  compact = false,
}: {
  className?: string;
  // Compact: on small screens show only the mark, to leave room for navigation.
  compact?: boolean;
}) {
  return (
    <Link
      href="/"
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-md text-[1.05rem] font-bold tracking-tight outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        className,
      )}
    >
      <BrandMark />
      <span className={compact ? "sr-only sm:not-sr-only" : undefined}>FakesNews</span>
    </Link>
  );
}
