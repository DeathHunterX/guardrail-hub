import { Check, ShieldAlert, X } from "lucide-react";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import {
  inScope,
  outOfScope,
  reportGuidelines,
  responseTimeline,
  safeHarbor,
  securityCopy,
} from "./data";

export function Security() {
  return (
    <>
      <PageHeader
        eyebrow={securityCopy.eyebrow}
        title={securityCopy.title}
        lede={securityCopy.lede}
      >
        <div
          data-reveal
          className="mt-6 flex flex-wrap items-center justify-center gap-3"
        >
          <Button asChild>
            <a href={`mailto:${securityCopy.reportEmail}`}>
              <ShieldAlert aria-hidden /> {securityCopy.reportEmail}
            </a>
          </Button>
        </div>
        <p data-reveal className="mt-3 text-xs text-muted-foreground">
          {securityCopy.pgpNote}
        </p>
      </PageHeader>

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Response timeline commitments. */}
          <dl
            data-reveal
            className="mx-auto grid max-w-4xl grid-cols-2 gap-4 md:grid-cols-4"
          >
            {responseTimeline.map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border bg-card p-5 text-center"
              >
                <dd className="text-2xl font-semibold tracking-tight">
                  {item.value}
                </dd>
                <dt className="mt-1 text-xs text-muted-foreground">
                  {item.label}
                </dt>
              </div>
            ))}
          </dl>

          {/* Scope columns. */}
          <div className="mx-auto mt-16 grid max-w-4xl gap-4 md:grid-cols-2">
            <Card data-reveal className="bg-card/60">
              <CardContent className="p-6">
                <h2 className="text-sm font-semibold">In scope</h2>
                <ul className="mt-4 space-y-3">
                  {inScope.map((item) => (
                    <li
                      key={item.slice(0, 40)}
                      className="flex gap-3 text-sm leading-relaxed text-muted-foreground"
                    >
                      <Check
                        className="mt-0.5 size-4 shrink-0 text-success"
                        aria-hidden
                      />
                      {item}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card data-reveal className="bg-card/60">
              <CardContent className="p-6">
                <h2 className="text-sm font-semibold">Out of scope</h2>
                <ul className="mt-4 space-y-3">
                  {outOfScope.map((item) => (
                    <li
                      key={item.slice(0, 40)}
                      className="flex gap-3 text-sm leading-relaxed text-muted-foreground"
                    >
                      <X
                        className="mt-0.5 size-4 shrink-0 text-destructive"
                        aria-hidden
                      />
                      {item}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          {/* Reporting guidelines. */}
          <section
            aria-labelledby="guidelines-heading"
            className="mx-auto mt-16 max-w-4xl"
          >
            <h2
              data-reveal
              id="guidelines-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              What a great report includes
            </h2>
            <ol className="mt-6 space-y-4">
              {reportGuidelines.map((guideline, index) => (
                <li
                  data-reveal
                  key={guideline.slice(0, 32)}
                  className="flex gap-4 rounded-2xl border bg-card/60 p-5"
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono text-sm font-semibold text-primary">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {guideline}
                  </p>
                </li>
              ))}
            </ol>
          </section>

          {/* Safe harbor. */}
          <section
            data-reveal
            aria-labelledby="safe-harbor-heading"
            className="mx-auto mt-16 max-w-4xl rounded-3xl border bg-muted/40 p-8 md:p-12"
          >
            <h2
              id="safe-harbor-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              {safeHarbor.heading}
            </h2>
            <div className="mt-4 space-y-4 text-sm leading-relaxed text-muted-foreground">
              {safeHarbor.paragraphs.map((paragraph) => (
                <p key={paragraph.slice(0, 48)}>{paragraph}</p>
              ))}
            </div>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
