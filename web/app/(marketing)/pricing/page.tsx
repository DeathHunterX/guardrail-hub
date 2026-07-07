import { Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { tiers } from "@/content/pricing";
import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  comparisonRows,
  pricingCta,
  pricingFaq,
  pricingPageCopy,
  tierDetails,
} from "./pricing-page.data";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Guardrail Hub plans compared — prices, seat roles, and the benefits of each tier, from free side projects to enterprise.",
};

/** Formats the monthly price cell for a tier. */
function priceLabel(monthly: number | null) {
  if (monthly === null) return "Custom";
  if (monthly === 0) return "$0";
  return `$${monthly}`;
}

export default function PricingPage() {
  return (
    <>
      <PageHeader
        eyebrow={pricingPageCopy.eyebrow}
        title={pricingPageCopy.title}
        lede={pricingPageCopy.lede}
      >
        <p data-reveal className="mt-4 text-xs text-muted-foreground">
          {pricingPageCopy.reassurance}
        </p>
      </PageHeader>

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Plan cards: shared tier data + page-only audience/roles/benefits. */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {tiers.map((tier) => {
              const detail = tierDetails.find(
                (entry) => entry.tierId === tier.id,
              );

              return (
                <Card
                  data-reveal
                  key={tier.id}
                  className={
                    tier.featured
                      ? "relative border-primary/50 bg-card/60 shadow-elevation-2"
                      : "bg-card/60"
                  }
                >
                  <CardContent className="flex h-full flex-col p-6">
                    {tier.featured ? (
                      <Badge className="absolute -top-2.5 left-6">
                        Most popular
                      </Badge>
                    ) : null}
                    <h2 className="text-sm font-semibold">{tier.name}</h2>
                    <p className="mt-3 flex items-baseline gap-1.5">
                      <span className="text-3xl font-semibold tracking-tight">
                        {priceLabel(tier.monthly)}
                      </span>
                      {tier.monthly ? (
                        <span className="text-xs text-muted-foreground">
                          / month
                        </span>
                      ) : null}
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {detail?.audience ?? tier.positioning}
                    </p>

                    {detail ? (
                      <>
                        {/* Seat roles unlocked by the plan. */}
                        <div className="mt-5">
                          <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                            Roles · {detail.seats}
                          </h3>
                          <ul className="mt-3 space-y-2.5">
                            {detail.roles.map((role) => (
                              <li key={role.name} className="text-sm">
                                <span className="font-medium">{role.name}</span>
                                <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                                  {role.description}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Why subscribe — outcome-level benefits. */}
                        <div className="mt-5 flex-1">
                          <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                            Why this plan
                          </h3>
                          <ul className="mt-3 space-y-2.5">
                            {detail.benefits.map((benefit) => (
                              <li
                                key={benefit.slice(0, 40)}
                                className="flex gap-2 text-xs leading-relaxed text-muted-foreground"
                              >
                                <Check
                                  className="mt-0.5 size-3.5 shrink-0 text-success"
                                  aria-hidden
                                />
                                {benefit}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </>
                    ) : null}

                    <Button
                      asChild
                      size="lg"
                      variant={tier.featured ? "default" : "outline"}
                      className="mt-6 w-full shrink-0 rounded-lg"
                    >
                      <Link href={tier.cta.href}>{tier.cta.label}</Link>
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Full comparison — real content buyers read, so a semantic table. */}
          <section aria-labelledby="comparison-heading" className="mt-20">
            <h2
              data-reveal
              id="comparison-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              Compare every plan
            </h2>
            <div data-reveal className="mt-6 overflow-x-auto rounded-2xl border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col" className="min-w-[220px] pl-4">
                      Capability
                    </TableHead>
                    {tiers.map((tier) => (
                      <TableHead scope="col" key={tier.id}>
                        {tier.name}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comparisonRows.map((row) => (
                    <TableRow key={row.capability}>
                      <TableCell className="pl-4 text-sm font-medium">
                        {row.capability}
                      </TableCell>
                      {row.values.map((value, index) => (
                        <TableCell
                          key={`${row.capability}-${tiers[index]?.id ?? index}`}
                          className="text-sm text-muted-foreground"
                        >
                          {value}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>

          {/* Pricing FAQ. */}
          <section
            aria-labelledby="pricing-faq-heading"
            className="mx-auto mt-20 max-w-3xl"
          >
            <h2
              data-reveal
              id="pricing-faq-heading"
              className="text-center text-2xl font-semibold tracking-tight"
            >
              Pricing questions
            </h2>
            <div data-reveal className="mt-6">
              <Accordion type="single" collapsible>
                {pricingFaq.map((item) => (
                  <AccordionItem key={item.question} value={item.question}>
                    <AccordionTrigger className="text-left text-sm font-medium">
                      {item.question}
                    </AccordionTrigger>
                    <AccordionContent className="text-sm leading-relaxed text-muted-foreground">
                      {item.answer}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          </section>

          {/* Closing CTA. */}
          <section
            data-reveal
            aria-label={pricingCta.title}
            className="mx-auto mt-20 max-w-3xl rounded-3xl border bg-muted/40 p-8 text-center md:p-12"
          >
            <h2 className="text-2xl font-semibold tracking-tight">
              {pricingCta.title}
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              {pricingCta.description}
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button asChild>
                <Link href={pricingCta.primary.href}>
                  {pricingCta.primary.label}
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={pricingCta.secondary.href}>
                  {pricingCta.secondary.label}
                </Link>
              </Button>
            </div>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
