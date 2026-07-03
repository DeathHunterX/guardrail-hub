"use client";

import { Github, Star } from "lucide-react";

import { AnimatedNumber } from "@/components/shared/animated-number";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";
import { formatCompactNumber } from "@/lib/utils";

interface GitHubStarsButtonProps {
  /** Star count fetched server-side; null when the API was unreachable. */
  stars: number | null;
}

/**
 * GitHub link with a live star count ([S->C] contract: the count arrives as
 * a prop from the server header, this component only animates it).
 */
export function GitHubStarsButton({ stars }: GitHubStarsButtonProps) {
  const label =
    stars === null
      ? "Guardrail Hub on GitHub"
      : `Guardrail Hub on GitHub — ${formatCompactNumber(stars)} stars`;

  return (
    <Button asChild variant="outline" size="sm">
      <a
        href={siteConfig.links.github}
        target="_blank"
        rel="noreferrer"
        aria-label={label}
      >
        <Github aria-hidden />
        <span className="hidden xl:inline">GitHub</span>
        {stars !== null ? (
          <span className="flex items-center gap-1 border-l pl-2 text-muted-foreground">
            <Star className="size-3.5" aria-hidden />
            <AnimatedNumber
              value={stars}
              format={formatCompactNumber}
              trigger="mount"
              className="text-xs font-medium"
            />
          </span>
        ) : null}
      </a>
    </Button>
  );
}
