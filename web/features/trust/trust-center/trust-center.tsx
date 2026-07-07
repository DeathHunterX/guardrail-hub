import { ArrowUpRight, BadgeCheck } from "lucide-react";
import Link from "next/link";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { StatusDot } from "@/components/common/status-dot";
import { RevealScope } from "@/components/effects/reveal-scope";
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
import { externalLinks } from "@/constants/external-links";

import {
  certifications,
  practices,
  subprocessors,
  trustCopy,
  trustLinks,
} from "./data";

export function TrustCenter() {
  return (
    <>
      <PageHeader
        eyebrow={trustCopy.eyebrow}
        title={trustCopy.title}
        lede={trustCopy.lede}
      >
        {/* Live status chip mirrors the footer's status affordance. */}
        <p data-reveal className="mt-6 flex justify-center">
          <a
            href={externalLinks.status}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border bg-card/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-success/40 hover:text-foreground"
          >
            <StatusDot status="success" pulse />
            All systems operational — view status page
          </a>
        </p>
      </PageHeader>

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Certifications. */}
          <section aria-labelledby="certifications-heading">
            <h2
              data-reveal
              id="certifications-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              Certifications & frameworks
            </h2>
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {certifications.map((cert) => (
                <Card data-reveal key={cert.name} className="bg-card/60">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between gap-2">
                      <BadgeCheck className="size-6 text-primary" aria-hidden />
                      <Badge variant="success">{cert.status}</Badge>
                    </div>
                    <h3 className="mt-4 text-sm font-semibold">{cert.name}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {cert.description}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          {/* Security practices. */}
          <section aria-labelledby="practices-heading" className="mt-20">
            <h2
              data-reveal
              id="practices-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              How we protect your data
            </h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {practices.map((practice) => (
                <Card data-reveal key={practice.title} className="bg-card/60">
                  <CardContent className="p-6">
                    <practice.icon className="size-6 text-primary" aria-hidden />
                    <h3 className="mt-4 text-sm font-semibold">
                      {practice.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {practice.description}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          {/* Subprocessors — real, reviewable content, so a semantic table. */}
          <section aria-labelledby="subprocessors-heading" className="mt-20">
            <h2
              data-reveal
              id="subprocessors-heading"
              className="text-2xl font-semibold tracking-tight"
            >
              Subprocessors
            </h2>
            <p data-reveal className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Third parties that may process customer data on our behalf. We
              give 30 days&apos; notice before any change — subscribe via the
              trust team.
            </p>
            <div data-reveal className="mt-6 overflow-hidden rounded-2xl border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col" className="pl-4">Provider</TableHead>
                    <TableHead scope="col">Purpose</TableHead>
                    <TableHead scope="col" className="pr-4">Location</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {subprocessors.map((subprocessor) => (
                    <TableRow key={subprocessor.name}>
                      <TableCell className="pl-4 text-sm font-medium">
                        {subprocessor.name}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {subprocessor.purpose}
                      </TableCell>
                      <TableCell className="pr-4 text-sm text-muted-foreground">
                        {subprocessor.location}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>

          {/* Documents + contact. */}
          <section
            data-reveal
            aria-label="Request documents"
            className="mx-auto mt-20 max-w-3xl rounded-3xl border bg-muted/40 p-8 text-center md:p-12"
          >
            <h2 className="text-2xl font-semibold tracking-tight">
              Running a security review?
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              We&apos;ll return completed questionnaires, audit reports, and a
              countersigned DPA — usually within two business days.
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button asChild>
                <a href={`mailto:${trustCopy.contactEmail}`}>
                  {trustCopy.contactEmail}
                </a>
              </Button>
            </div>
            <ul className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm">
              {trustLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="group inline-flex items-center gap-1 font-medium text-primary"
                  >
                    {link.label}
                    <ArrowUpRight
                      className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
                      aria-hidden
                    />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
