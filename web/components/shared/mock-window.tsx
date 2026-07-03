import type { ReactNode } from "react";

import { GlassPanel } from "@/components/shared/glass-panel";
import { cn } from "@/lib/utils";

interface MockWindowProps {
  title?: string;
  /** "browser" adds a URL pill next to the traffic lights. */
  variant?: "app" | "browser";
  url?: string;
  elevation?: 1 | 2 | 3;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

/**
 * Window chrome for every product simulation (spec §0.5): traffic-light dots,
 * optional title / URL bar, glass body. Decorative by design — consumers set
 * the accessible semantics on their own wrapper.
 */
export function MockWindow({
  title,
  variant = "app",
  url,
  elevation = 3,
  className,
  contentClassName,
  children,
}: MockWindowProps) {
  return (
    <GlassPanel
      elevation={elevation}
      className={cn("overflow-hidden", className)}
    >
      <div className="flex items-center gap-3 border-b bg-muted/40 px-4 py-2.5">
        <span className="flex gap-1.5" aria-hidden="true">
          <span className="size-2.5 rounded-full bg-destructive/70" />
          <span className="size-2.5 rounded-full bg-warning/70" />
          <span className="size-2.5 rounded-full bg-success/70" />
        </span>
        {variant === "browser" && url ? (
          <span className="mx-auto flex min-w-0 items-center rounded-md border bg-background/60 px-3 py-0.5 font-mono text-[11px] text-muted-foreground">
            <span className="truncate">{url}</span>
          </span>
        ) : title ? (
          <span className="text-xs font-medium text-muted-foreground">
            {title}
          </span>
        ) : null}
      </div>
      <div className={cn("p-4", contentClassName)}>{children}</div>
    </GlassPanel>
  );
}
