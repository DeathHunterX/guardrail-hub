import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

const elevationClasses = {
  1: "shadow-sm",
  2: "shadow-elevation-2",
  3: "shadow-elevation-3 dark:ring-1 dark:ring-white/10",
} as const;

interface GlassPanelProps extends ComponentPropsWithoutRef<"div"> {
  elevation?: keyof typeof elevationClasses;
}

/** Floating glass surface (spec §0.5) — the base of every mock-UI panel. */
export function GlassPanel({
  elevation = 2,
  className,
  ...props
}: GlassPanelProps) {
  return (
    <div
      className={cn(
        "glass-surface rounded-2xl",
        elevationClasses[elevation],
        className,
      )}
      {...props}
    />
  );
}
