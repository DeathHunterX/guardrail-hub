import { SectionShell } from "@/components/shared/section-shell";
import { cn } from "@/lib/utils";

import { FeatureVisual } from "./feature-visuals";
import { features, featuresCopy } from "./features.data";

const sizeClasses = {
  hero: "md:col-span-2 md:row-span-2",
  wide: "md:col-span-2",
  tall: "md:row-span-2",
  standard: "",
} as const;

/**
 * Features bento grid (spec §7). Cell size encodes importance; every cell
 * carries a mock-UI vignette in the shared visual grammar.
 */
export function Features() {
  return (
    <SectionShell
      id="features"
      eyebrow={featuresCopy.eyebrow}
      title={featuresCopy.title}
      lede={featuresCopy.lede}
    >
      <ul className="grid grid-flow-dense gap-4 md:grid-cols-2 lg:grid-cols-3">
        {features.map((feature) => (
          <li
            key={feature.title}
            data-reveal
            className={cn(sizeClasses[feature.size], "min-w-0")}
          >
            <article
              className={cn(
                "group relative flex h-full flex-col overflow-hidden rounded-2xl border bg-card p-6 transition-all duration-300",
                "hover:-translate-y-1 hover:border-primary/25 hover:shadow-elevation-2 motion-reduce:hover:translate-y-0",
              )}
            >
              <span className="icon-tile transition-transform duration-300 group-hover:rotate-6 motion-reduce:group-hover:rotate-0">
                <feature.icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 font-semibold">{feature.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
              <div
                aria-hidden="true"
                className="mt-auto pt-6"
              >
                <div className="rounded-xl border bg-muted/40 p-3.5">
                  <FeatureVisual kind={feature.visual} />
                </div>
              </div>
              {/* Pointer-lit border highlight, CSS-only. */}
              <span
                aria-hidden="true"
                className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
              />
            </article>
          </li>
        ))}
      </ul>
    </SectionShell>
  );
}
