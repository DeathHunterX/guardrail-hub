import { Quote } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { featured, testimonials } from "@/content/testimonials";

import {
  customersCta,
  customersPageCopy,
  outcomeStats,
} from "./customers-page.data";

export const metadata: Metadata = {
  title: "Customers",
  description:
    "What early adopters do with Guardrail Hub, in their own words — outcomes, metrics, and testimonials from teams that ship.",
};

/** Two-letter initials for the avatar fallback. */
function initialsOf(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2);
}

function AttributionRow({
  name,
  role,
  company,
}: {
  name: string;
  role: string;
  company: string;
}) {
  return (
    <figcaption className="mt-5 flex items-center gap-3">
      <Avatar className="size-9">
        <AvatarFallback className="text-xs font-semibold">
          {initialsOf(name)}
        </AvatarFallback>
      </Avatar>
      <span className="min-w-0 text-sm">
        <span className="block font-medium">{name}</span>
        <span className="block text-xs text-muted-foreground">
          {role} · {company}
        </span>
      </span>
    </figcaption>
  );
}

export default function CustomersPage() {
  return (
    <>
      <PageHeader
        eyebrow={customersPageCopy.eyebrow}
        title={customersPageCopy.title}
        lede={customersPageCopy.lede}
      />

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Featured story. */}
          <figure
            data-reveal
            className="relative mx-auto max-w-4xl rounded-3xl border bg-card/60 p-8 md:p-12"
          >
            <Quote
              aria-hidden
              className="absolute right-8 top-8 size-8 text-primary/20"
            />
            {featured.metric ? (
              <Badge variant="success">{featured.metric}</Badge>
            ) : null}
            <blockquote className="mt-4 text-balance text-xl font-medium leading-relaxed md:text-2xl">
              “{featured.quote}”
            </blockquote>
            <AttributionRow
              name={featured.name}
              role={featured.role}
              company={featured.company}
            />
          </figure>

          {/* Outcome stats pulled from the stories below. */}
          <dl
            data-reveal
            className="mx-auto mt-12 grid max-w-4xl grid-cols-2 gap-4 md:grid-cols-4"
          >
            {outcomeStats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border bg-card p-5 text-center"
              >
                <dd className="text-2xl font-semibold tracking-tight">
                  {stat.value}
                </dd>
                <dt className="mt-1 text-xs text-muted-foreground">
                  {stat.label}
                </dt>
              </div>
            ))}
          </dl>

          {/* Testimonial wall — the full set, readable instead of a marquee. */}
          <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {testimonials.map((testimonial) => (
              <Card data-reveal key={testimonial.name} className="bg-card/60">
                <CardContent className="flex h-full flex-col p-6">
                  {testimonial.metric ? (
                    <Badge variant="success" className="self-start">
                      {testimonial.metric}
                    </Badge>
                  ) : null}
                  <blockquote className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">
                    “{testimonial.quote}”
                  </blockquote>
                  <AttributionRow
                    name={testimonial.name}
                    role={testimonial.role}
                    company={testimonial.company}
                  />
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Closing CTA. */}
          <section
            data-reveal
            aria-label={customersCta.title}
            className="mx-auto mt-20 max-w-3xl rounded-3xl border bg-muted/40 p-8 text-center md:p-12"
          >
            <h2 className="text-2xl font-semibold tracking-tight">
              {customersCta.title}
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              {customersCta.description}
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button asChild>
                <Link href={customersCta.primary.href}>
                  {customersCta.primary.label}
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={customersCta.secondary.href}>
                  {customersCta.secondary.label}
                </Link>
              </Button>
            </div>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
