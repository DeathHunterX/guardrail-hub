import type { ReactNode } from "react";

import { Logo } from "@/components/layout/logo";
import { cn } from "@/lib/utils";

interface AuthCardProps {
  title: string;
  description?: string;
  children: ReactNode;
  /** Links below the card body — "Don't have an account?" etc. */
  footer?: ReactNode;
  className?: string;
}

/**
 * Shared shell for every auth screen: brand mark, heading cadence, and the
 * landing page's glass surface so signing in feels like the same product.
 */
export function AuthCard({
  title,
  description,
  children,
  footer,
  className,
}: AuthCardProps) {
  return (
    <div className={cn("w-full max-w-md", className)}>
      <div className="flex justify-center">
        <Logo />
      </div>
      <div className="glass-surface mt-8 rounded-2xl p-6 shadow-elevation-2 sm:p-8">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description ? (
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        <div className="mt-6">{children}</div>
      </div>
      {footer ? (
        <div className="mt-6 text-center text-sm text-muted-foreground">
          {footer}
        </div>
      ) : null}
    </div>
  );
}
