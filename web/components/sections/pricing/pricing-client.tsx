"use client";

import { Check, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AnimatedNumber } from "@/components/shared/animated-number";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { durations } from "@/lib/gsap/motion";
import { cn } from "@/lib/utils";

import { pricingCopy, tiers, type Tier } from "./pricing.data";

function priceFor(tier: Tier, annual: boolean): number | null {
  if (tier.monthly === null || tier.monthly === 0) return tier.monthly;
  return annual
    ? Math.round(tier.monthly * pricingCopy.annualDiscount)
    : tier.monthly;
}

function TierCard({ tier, annual }: { tier: Tier; annual: boolean }) {
  const price = priceFor(tier, annual);
  return (
    <article
      data-reveal
      className={cn(
        "relative flex h-full flex-col rounded-2xl border bg-card p-6 transition-all duration-300",
        tier.featured
          ? // The featured tier leads the stack on mobile via CSS order.
            "order-first border-primary shadow-elevation-3 lg:order-none lg:-my-4 lg:py-10"
          : "hover:-translate-y-1 hover:shadow-elevation-2 motion-reduce:hover:translate-y-0",
      )}
    >
      {tier.featured ? (
        <>
          <span
            aria-hidden="true"
            className="absolute inset-x-6 top-0 h-px bg-brand-gradient"
          />
          <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 gap-1">
            <Sparkles className="size-3" aria-hidden /> Most popular
          </Badge>
        </>
      ) : null}
      <h3 className="font-semibold">{tier.name}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{tier.positioning}</p>
      <p className="mt-5 flex items-baseline gap-1" aria-live="polite">
        {price === null ? (
          <span className="text-3xl font-semibold tracking-tight">Custom</span>
        ) : (
          <>
            <span className="text-3xl font-semibold tracking-tight">
              $
              <AnimatedNumber
                value={price}
                trigger="mount"
                duration={durations.sm}
              />
            </span>
            <span className="text-sm text-muted-foreground">
              /user/mo{annual ? ", billed annually" : ""}
            </span>
          </>
        )}
      </p>
      <ul className="mt-6 flex-1 space-y-2.5">
        {tier.features.map((feature) => (
          <li key={feature} className="flex gap-2 text-sm text-muted-foreground">
            <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            {feature}
          </li>
        ))}
      </ul>
      {/* Fixed height keeps every tier's CTA button exactly the same size. */}
      <Button
        asChild
        variant={tier.featured ? "default" : "outline"}
        className={cn("mt-8 h-10 w-full", tier.featured && "btn-sheen")}
      >
        <Link href={tier.cta.href}>{tier.cta.label}</Link>
      </Button>
    </article>
  );
}

/** Pricing grid + billing toggle (spec §13). Pro leads the stack on mobile. */
export function PricingClient() {
  const [annual, setAnnual] = useState(true);

  return (
    <div>
      <div
        data-reveal
        className="mb-12 flex items-center justify-center gap-3 text-sm"
      >
        <Label htmlFor="billing-toggle" className="text-muted-foreground">
          Monthly
        </Label>
        <Switch
          id="billing-toggle"
          checked={annual}
          onCheckedChange={setAnnual}
          aria-label={`Billing period: ${annual ? "annual, save 20%" : "monthly"}`}
        />
        <Label htmlFor="billing-toggle" className="flex items-center gap-2">
          Annual
          <Badge variant="success" className="text-[10px]">
            Save 20%
          </Badge>
        </Label>
      </div>

      {/* Single grid for all breakpoints: featured leads on mobile through
          CSS order, so no duplicate (display:none) card set exists — the
          desktop copy could be skipped by the reveal animation and render
          the section blank on large screens. */}
      <div className="grid items-stretch gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {tiers.map((tier) => (
          <TierCard key={tier.id} tier={tier} annual={annual} />
        ))}
      </div>

      <p
        data-reveal
        className="mt-10 text-center text-sm text-muted-foreground"
      >
        {pricingCopy.reassurance}
      </p>
    </div>
  );
}
