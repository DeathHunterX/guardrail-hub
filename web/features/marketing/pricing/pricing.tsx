import { ArrowUpRight } from "lucide-react";

import { SectionShell } from "@/components/common/section-shell";

import { PricingClient } from "./pricing-client";
import { pricingCopy } from "./data";

/** Pricing Preview (spec §13). Zero decoration — whitespace does the luxury work. */
export function Pricing() {
  return (
    <SectionShell
      id="pricing"
      eyebrow={pricingCopy.eyebrow}
      title={pricingCopy.title}
    >
      <PricingClient />
      <p data-reveal className="mt-4 text-center text-sm">
        <a
          href="/pricing"
          className="group inline-flex items-center gap-1 font-medium text-primary"
        >
          Compare all features
          <ArrowUpRight
            className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
            aria-hidden
          />
        </a>
      </p>
    </SectionShell>
  );
}
