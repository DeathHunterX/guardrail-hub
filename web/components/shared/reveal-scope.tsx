"use client";

import type { ReactNode } from "react";

import { useSectionReveal } from "@/lib/gsap/use-section-reveal";
import { cn } from "@/lib/utils";

interface RevealScopeProps {
  className?: string;
  children: ReactNode;
}

/**
 * Client boundary that applies the house-style reveal to all `[data-reveal]`
 * descendants. Sections get consistent entrance animation by markup
 * convention — never by reimplementing the timeline.
 */
export function RevealScope({ className, children }: RevealScopeProps) {
  const scope = useSectionReveal<HTMLDivElement>();

  return (
    <div ref={scope} className={cn(className)}>
      {children}
    </div>
  );
}
