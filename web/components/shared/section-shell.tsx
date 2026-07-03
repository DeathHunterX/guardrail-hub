import type { ReactNode } from "react";

import { Container } from "@/components/shared/container";
import { RevealScope } from "@/components/shared/reveal-scope";
import { cn } from "@/lib/utils";

interface SectionShellProps {
  /** Anchor id — also derives the heading id for aria-labelledby. */
  id: string;
  /** Uppercase eyebrow label above the title. */
  eyebrow: string;
  title: string;
  lede?: string;
  /**
   * "center": header centered, content below (most sections).
   * "left": header left-aligned — used by split-layout sections that place
   * content beside the header inside `children`.
   */
  align?: "center" | "left";
  className?: string;
  children: ReactNode;
}

/**
 * The standard section scaffold (spec §0.5): consistent vertical rhythm,
 * the eyebrow -> H2 -> lede header cadence, semantic labelling, and the
 * house reveal via RevealScope.
 */
export function SectionShell({
  id,
  eyebrow,
  title,
  lede,
  align = "center",
  className,
  children,
}: SectionShellProps) {
  const headingId = `${id}-heading`;
  const centered = align === "center";

  // Vertical rhythm: ~100-110px total gap between adjacent sections
  // (2 x 48-56px of padding).
  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className={cn("py-12 md:py-14", className)}
    >
      <Container>
        <RevealScope>
          <div
            className={cn(
              "mb-10 md:mb-12",
              centered && "mx-auto max-w-3xl text-center",
            )}
          >
            <p
              data-reveal
              className="text-[0.8125rem] font-medium uppercase tracking-widest text-muted-foreground"
            >
              {eyebrow}
            </p>
            <h2
              data-reveal
              id={headingId}
              className="mt-3 text-balance text-heading-2"
            >
              {title}
            </h2>
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
          </div>
          {children}
        </RevealScope>
      </Container>
    </section>
  );
}
