import { ArrowUpRight } from "lucide-react";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { benefits, careersCopy, hiringProcess, roles } from "./data";

/** Builds a prefilled application mailto link for a role. */
function applyHref(roleTitle: string) {
  const subject = encodeURIComponent(`Application: ${roleTitle}`);
  return `mailto:${careersCopy.applyEmail}?subject=${subject}`;
}

export function Careers() {
  return (
    <>
      <PageHeader
        eyebrow={careersCopy.eyebrow}
        title={careersCopy.title}
        lede={careersCopy.lede}
      />

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Open roles. */}
          <section aria-labelledby="roles-heading">
            <h2
              data-reveal
              id="roles-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              Open roles
              <span className="ml-3 align-middle">
                <Badge variant="secondary">{roles.length} positions</Badge>
              </span>
            </h2>
            <ul className="mt-6 space-y-3">
              {roles.map((role) => (
                <li data-reveal key={role.title}>
                  <Card className="bg-card/60 transition-colors hover:border-primary/40">
                    <CardContent className="flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between">
                      <div className="min-w-0">
                        <h3 className="text-base font-semibold">{role.title}</h3>
                        <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                          {role.summary}
                        </p>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <Badge variant="outline">{role.team}</Badge>
                          <span>{role.location}</span>
                          <span aria-hidden="true">·</span>
                          <span>{role.type}</span>
                        </div>
                      </div>
                      <Button asChild className="shrink-0">
                        <a href={applyHref(role.title)}>
                          Apply <ArrowUpRight aria-hidden />
                        </a>
                      </Button>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
            <p data-reveal className="mt-4 text-sm text-muted-foreground">
              Nothing that fits? We keep a warm bench — send a note to{" "}
              <a
                href={`mailto:${careersCopy.applyEmail}`}
                className="font-medium text-foreground hover:text-primary"
              >
                {careersCopy.applyEmail}
              </a>{" "}
              and tell us what you&apos;d want to own.
            </p>
          </section>

          {/* Benefits grid. */}
          <section aria-labelledby="benefits-heading" className="mt-20">
            <h2
              data-reveal
              id="benefits-heading"
              className="text-center text-2xl font-semibold tracking-tight"
            >
              How we take care of the team
            </h2>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {benefits.map((benefit) => (
                <Card data-reveal key={benefit.title} className="bg-card/60">
                  <CardContent className="p-6">
                    <benefit.icon className="size-6 text-primary" aria-hidden />
                    <h3 className="mt-4 text-sm font-semibold">
                      {benefit.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {benefit.description}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          {/* Hiring process. */}
          <section
            aria-labelledby="process-heading"
            className="mx-auto mt-20 max-w-3xl"
          >
            <h2
              data-reveal
              id="process-heading"
              className="text-center text-2xl font-semibold tracking-tight"
            >
              The process, start to finish
            </h2>
            <ol className="mt-8 space-y-4">
              {hiringProcess.map((step, index) => (
                <li
                  data-reveal
                  key={step.slice(0, 32)}
                  className="flex gap-4 rounded-2xl border bg-card/60 p-5"
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono text-sm font-semibold text-primary">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {step}
                  </p>
                </li>
              ))}
            </ol>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
