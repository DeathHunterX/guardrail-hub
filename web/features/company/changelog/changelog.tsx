import { ArrowUpRight, Github } from "lucide-react";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { changelogCopy, changelogCta, releases } from "./data";
import type { UpdateKind } from "./types";

/** Badge variant per update kind — mirrors the severity chip language. */
const kindVariant: Record<UpdateKind, "success" | "secondary" | "warning"> = {
  New: "success",
  Improved: "secondary",
  Fixed: "warning",
};

export function Changelog() {
  return (
    <>
      <PageHeader
        eyebrow={changelogCopy.eyebrow}
        title={changelogCopy.title}
        lede={changelogCopy.lede}
      />

      <Container size="narrow" className="pb-20 md:pb-28">
        <RevealScope>
          <ol className="relative space-y-14 border-l pl-8 md:space-y-16">
            {releases.map((release) => (
              <li data-reveal key={release.version} className="relative">
                {/* Timeline marker. */}
                <span
                  aria-hidden="true"
                  className="absolute -left-[2.4rem] top-1.5 size-3 rounded-full border-2 border-background bg-primary"
                />

                {/* Release meta row. */}
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold">
                    {release.version}
                  </span>
                  <Badge variant="warning">{release.stage}</Badge>
                  {release.latest ? <Badge>Latest</Badge> : null}
                  <time className="text-xs text-muted-foreground">
                    {release.date}
                  </time>
                </div>

                <h2 className="mt-3 text-balance text-xl font-semibold tracking-tight md:text-2xl">
                  {release.title}
                </h2>

                {/* Overview — the "why" of the release. */}
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {release.overview}
                </p>

                {/* Key updates; the exhaustive list lives in the release notes. */}
                <ul className="mt-5 space-y-2.5">
                  {release.highlights.map((update) => (
                    <li
                      key={update.text.slice(0, 48)}
                      className="flex items-start gap-3 text-sm leading-relaxed"
                    >
                      <Badge
                        variant={kindVariant[update.kind]}
                        className="mt-0.5 w-[4.5rem] shrink-0 justify-center"
                      >
                        {update.kind}
                      </Badge>
                      <span className="text-muted-foreground">
                        {update.text}
                      </span>
                    </li>
                  ))}
                </ul>

                {/* Full notes live with the GitHub release. */}
                <p className="mt-5">
                  <a
                    href={release.detailUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="group inline-flex items-center gap-1 text-sm font-medium text-primary"
                  >
                    Read the full {release.version} release notes
                    <ArrowUpRight
                      className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
                      aria-hidden
                    />
                  </a>
                </p>
              </li>
            ))}
          </ol>

          {/* Follow CTA. */}
          <section
            data-reveal
            aria-label={changelogCta.title}
            className="mt-20 rounded-3xl border bg-muted/40 p-8 text-center md:p-12"
          >
            <h2 className="text-2xl font-semibold tracking-tight">
              {changelogCta.title}
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              {changelogCta.description}
            </p>
            <div className="mt-6 flex justify-center">
              <Button asChild>
                <a
                  href={changelogCta.action.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Github aria-hidden /> {changelogCta.action.label}
                </a>
              </Button>
            </div>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
