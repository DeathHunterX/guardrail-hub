import { ArrowUpRight, BadgeCheck, Check } from "lucide-react";

import { MockWindow } from "@/components/shared/mock-window";
import { SectionShell } from "@/components/shared/section-shell";
import { StatusDot } from "@/components/shared/status-dot";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { siteConfig } from "@/config/site";

import {
  certifications,
  complianceCopy,
  controls,
  coverage,
} from "./compliance.data";

/**
 * Compliance (spec §11). The matrix is real, readable content — compliance
 * buyers will read it — so it's a semantic table, not a decorative mock.
 * Motion whispers here: one reveal pass, then stillness. Stillness = stability.
 */
export function Compliance() {
  return (
    <SectionShell
      id="compliance"
      eyebrow={complianceCopy.eyebrow}
      title={complianceCopy.title}
      lede={complianceCopy.lede}
      align="left"
    >
      <div className="grid gap-12 lg:grid-cols-12">
        <div data-reveal className="min-w-0 lg:col-span-7">
          <MockWindow title="Compliance · acme-platform" contentClassName="p-0">
            <p className="border-b px-4 py-2.5 font-mono text-xs text-muted-foreground">
              {coverage}
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col" className="pl-4">Control</TableHead>
                  <TableHead scope="col" className="hidden sm:table-cell">
                    Evidence
                  </TableHead>
                  <TableHead scope="col">Status</TableHead>
                  <TableHead scope="col" className="hidden pr-4 md:table-cell">
                    Last validated
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {controls.map((row) => (
                  <TableRow key={row.control}>
                    <TableCell className="pl-4 font-mono text-xs">
                      {row.control}
                    </TableCell>
                    <TableCell className="hidden text-xs text-muted-foreground sm:table-cell">
                      {row.evidence}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={row.status === "passing" ? "success" : "warning"}
                        className="gap-1 px-1.5 text-[10px]"
                      >
                        <StatusDot
                          status={row.status === "passing" ? "success" : "warning"}
                        />
                        {row.status === "passing" ? "Passing" : "Attention"}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden pr-4 text-xs text-muted-foreground md:table-cell">
                      {row.validated}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </MockWindow>
        </div>

        <div className="lg:col-span-5">
          <ul className="space-y-4">
            {complianceCopy.bullets.map((bullet) => (
              <li key={bullet} data-reveal className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                {bullet}
              </li>
            ))}
          </ul>
          <div data-reveal className="mt-8 grid grid-cols-3 gap-3">
            {certifications.map((cert) => (
              <div
                key={cert.name}
                className="flex flex-col items-center gap-1.5 rounded-2xl border bg-card p-4 text-center"
              >
                <BadgeCheck className="size-6 text-primary" aria-hidden />
                <span className="text-xs font-semibold leading-tight">
                  {cert.name}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {cert.detail}
                </span>
              </div>
            ))}
          </div>
          <p data-reveal className="mt-6 text-sm">
            <a
              href={`${siteConfig.url}/trust`}
              className="group inline-flex items-center gap-1 font-medium text-primary"
            >
              View our trust center
              <ArrowUpRight
                className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
                aria-hidden
              />
            </a>
          </p>
        </div>
      </div>
    </SectionShell>
  );
}
