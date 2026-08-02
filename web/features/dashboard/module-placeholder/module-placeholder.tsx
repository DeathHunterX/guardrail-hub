import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";
import { externalLinks } from "@/constants/external-links";

import { placeholderModules, type PlaceholderModuleId } from "./data";

interface ModulePlaceholderProps {
  module: PlaceholderModuleId;
}

/**
 * Consistent "coming soon" page for navigable modules whose backend doesn't
 * exist yet (see content/app.ts `planned`). Honest by design: it names what
 * the module will do and what it's waiting on, instead of faking data.
 */
export function ModulePlaceholder({ module }: ModulePlaceholderProps) {
  const copy = placeholderModules[module];

  return (
    <div className="flex min-h-[60vh] flex-col">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{copy.title}</h1>
        <Badge variant="secondary">Coming soon</Badge>
      </div>
      <div className="mt-6 flex flex-1 items-center justify-center rounded-2xl border border-dashed">
        <EmptyState
          icon={copy.icon}
          title={`${copy.title} isn't available yet`}
          description={copy.description}
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href={siteConfig.app.dashboard}>Back to dashboard</Link>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <a href={externalLinks.docs} target="_blank" rel="noreferrer">
                  Read the docs
                </a>
              </Button>
            </div>
          }
        />
      </div>
    </div>
  );
}
