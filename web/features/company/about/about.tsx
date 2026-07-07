import Link from "next/link";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { aboutCopy, aboutCta, stats, story, values } from "./data";

export function About() {
  return (
    <>
      <PageHeader
        eyebrow={aboutCopy.eyebrow}
        title={aboutCopy.title}
        lede={aboutCopy.lede}
      />

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Founding story — narrow measure for comfortable reading. */}
          <section aria-labelledby="story-heading" className="mx-auto max-w-3xl">
            <h2
              data-reveal
              id="story-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              {story.heading}
            </h2>
            <div className="mt-5 space-y-4 text-[0.9375rem] leading-relaxed text-muted-foreground">
              {story.paragraphs.map((paragraph) => (
                <p data-reveal key={paragraph.slice(0, 48)}>
                  {paragraph}
                </p>
              ))}
            </div>
          </section>

          {/* Company stats. */}
          <dl
            data-reveal
            className="mx-auto mt-14 grid max-w-4xl grid-cols-2 gap-4 md:grid-cols-4"
          >
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border bg-card p-5 text-center"
              >
                <dd className="text-3xl font-semibold tracking-tight">
                  {stat.value}
                </dd>
                <dt className="mt-1 text-xs text-muted-foreground">
                  {stat.label}
                </dt>
              </div>
            ))}
          </dl>

          {/* Values grid. */}
          <section aria-labelledby="values-heading" className="mt-20">
            <h2
              data-reveal
              id="values-heading"
              className="text-center text-2xl font-semibold tracking-tight"
            >
              What we optimize for
            </h2>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {values.map((value) => (
                <Card data-reveal key={value.title} className="bg-card/60">
                  <CardContent className="p-6">
                    <value.icon className="size-6 text-primary" aria-hidden />
                    <h3 className="mt-4 text-sm font-semibold">{value.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {value.description}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          {/* Closing CTA. */}
          <section
            data-reveal
            aria-label={aboutCta.title}
            className="mx-auto mt-20 max-w-3xl rounded-3xl border bg-muted/40 p-8 text-center md:p-12"
          >
            <h2 className="text-2xl font-semibold tracking-tight">
              {aboutCta.title}
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              {aboutCta.description}
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button asChild>
                <Link href={aboutCta.primary.href}>{aboutCta.primary.label}</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={aboutCta.secondary.href}>
                  {aboutCta.secondary.label}
                </Link>
              </Button>
            </div>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
