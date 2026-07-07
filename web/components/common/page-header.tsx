import type { ReactNode } from "react";

import { Container } from "@/components/common/container";
import { RevealScope } from "@/components/effects/reveal-scope";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  /** Uppercase eyebrow label above the title. */
  eyebrow: string;
  title: string;
  lede?: string;
  /** "center" for standalone pages, "left" for document-style pages. */
  align?: "center" | "left";
  /** Extra content below the lede — badges, CTAs, meta rows. */
  children?: ReactNode;
  className?: string;
}

/**
 * Subpage hero: the H1 counterpart of SectionShell's H2 cadence
 * (eyebrow -> H1 -> lede). Used by every marketing subpage so headers
 * stay consistent with the landing page rhythm.
 */
export function PageHeader({
  eyebrow,
  title,
  lede,
  align = "center",
  children,
  className,
}: PageHeaderProps) {
  const centered = align === "center";

  return (
    <div className={cn("pb-10 pt-16 md:pb-14 md:pt-24", className)}>
      <Container>
        <RevealScope>
          <div className={cn(centered && "mx-auto max-w-3xl text-center")}>
            <p
              data-reveal
              className="text-[0.8125rem] font-medium uppercase tracking-widest text-muted-foreground"
            >
              {eyebrow}
            </p>
            <h1
              data-reveal
              className="mt-3 text-balance text-4xl font-semibold tracking-tight md:text-5xl"
            >
              {title}
            </h1>
            {lede ? (
              <p
                data-reveal
                className={cn(
                  "mt-4 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground",
                  centered && "mx-auto",
                )}
              >
                {lede}
              </p>
            ) : null}
            {children}
          </div>
        </RevealScope>
      </Container>
    </div>
  );
}
