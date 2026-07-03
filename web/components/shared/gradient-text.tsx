import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface GradientTextProps {
  className?: string;
  children: ReactNode;
}

/** Signature-gradient text fill. Convention: at most one per viewport. */
export function GradientText({ className, children }: GradientTextProps) {
  return (
    <span
      className={cn(
        "bg-brand-gradient bg-clip-text text-transparent",
        className,
      )}
    >
      {children}
    </span>
  );
}
