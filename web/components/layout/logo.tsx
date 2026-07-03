import Link from "next/link";

import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
}

/**
 * Brand mark: rounded shield containing a pulse line — security + liveness
 * (spec §2). The mark tilts 8 degrees on hover and settles back.
 */
export function Logo({ className }: LogoProps) {
  return (
    <Link
      href="/"
      aria-label="Guardrail Hub — home"
      className={cn("group flex items-center gap-2.5", className)}
    >
      <span className="flex size-8 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-elevation-2 transition-transform duration-300 group-hover:rotate-[8deg] motion-reduce:transition-none">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.8}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="size-5"
          aria-hidden="true"
        >
          <path d="M12 3l7 3v5.5c0 4.4-2.9 8-7 9.5-4.1-1.5-7-5.1-7-9.5V6l7-3z" />
          <path d="M8 12.5h2l1-2.5 1.6 4 1-1.5h2.4" />
        </svg>
      </span>
      <span className="text-base font-semibold tracking-tight">
        Guardrail Hub
      </span>
    </Link>
  );
}
