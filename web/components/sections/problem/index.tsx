import { AlertTriangle, ArrowRight, Unlink2 } from "lucide-react";
import { Fragment } from "react";

import { SectionShell } from "@/components/shared/section-shell";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import {
  evidenceScatter,
  glueSteps,
  pains,
  problemClosing,
  problemCopy,
  severityRows,
  statusQuoChain,
  type Pain,
} from "./problem.data";

/** Bar tone -> token classes; warm palette dominates this section only. */
const severityTones = {
  destructive: "bg-destructive",
  warning: "bg-warning",
  "warning-soft": "bg-warning/50",
  neutral: "bg-muted-foreground/40",
} as const;

const MAX_SEVERITY = Math.max(...severityRows.map((row) => row.count));

/**
 * Mini "chaos vignettes" (spec §5): each one recreates a scene the visitor
 * already lives in — disconnected tools, a manual relay, an alert wall,
 * scattered evidence — instead of describing it.
 */
function Vignette({ kind }: { kind: Pain["vignette"] }) {
  if (kind === "sprawl") {
    // Disconnected consoles: broken links between tools, nothing shared.
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {["ZAP", "Nuclei", "Trivy", "Semgrep"].map((tool, index) => (
            <Fragment key={tool}>
              {index > 0 ? (
                <Unlink2
                  className="size-3 shrink-0 text-destructive/60"
                  aria-hidden
                />
              ) : null}
              <span className="rounded-md border border-dashed border-destructive/30 px-2 py-1 font-mono text-[10px] text-muted-foreground">
                {tool}
              </span>
            </Fragment>
          ))}
        </div>
        <p className="font-mono text-[10px] text-muted-foreground">
          shared history: <span className="text-destructive">none</span> ·
          shared ownership: <span className="text-destructive">none</span>
        </p>
      </div>
    );
  }
  if (kind === "gluecode") {
    // The hand-rolled relay: every arrow is a script someone maintains.
    return (
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-2">
        {glueSteps.map((step, index) => (
          <Fragment key={step}>
            {index > 0 ? (
              <span
                aria-hidden="true"
                className="font-mono text-[10px] text-destructive/60"
              >
                →
              </span>
            ) : null}
            <span className="rounded-md border border-dashed px-2 py-1 font-mono text-[10px] text-muted-foreground">
              {step}
            </span>
          </Fragment>
        ))}
      </div>
    );
  }
  if (kind === "findings") {
    // Alert fatigue as a dashboard: big bars, empty ownership columns.
    return (
      <div className="space-y-2">
        {severityRows.map((row) => (
          <div key={row.label} className="flex items-center gap-2">
            <span className="w-14 shrink-0 font-mono text-[10px] text-muted-foreground">
              {row.label}
            </span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <span
                className={cn(
                  "block h-full rounded-full",
                  severityTones[row.tone],
                )}
                style={{ width: `${(row.count / MAX_SEVERITY) * 100}%` }}
              />
            </span>
            <span className="w-8 shrink-0 text-right font-mono text-[10px] text-muted-foreground">
              {row.count}
            </span>
          </div>
        ))}
        <p className="pt-1 font-mono text-[10px] text-muted-foreground">
          owner: — · priority: — · status: open
        </p>
      </div>
    );
  }
  // Audit vignette: evidence scattered across tools, some simply missing.
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {evidenceScatter.map((place) => (
          <span
            key={place}
            className={cn(
              "rounded-md border border-dashed px-2 py-1 font-mono text-[10px]",
              place === "???"
                ? "border-destructive/40 text-destructive"
                : "text-muted-foreground",
            )}
          >
            {place}
          </span>
        ))}
      </div>
      <Badge variant="warning" className="gap-1 px-2">
        <AlertTriangle className="size-3" /> SOC 2 — evidence missing · audit
        in 14 days
      </Badge>
    </div>
  );
}

/** Problem (spec §5): narrative header + 2x2 pain grid + emotional close. */
export function Problem() {
  return (
    <SectionShell
      id="problem"
      eyebrow={problemCopy.eyebrow}
      title={problemCopy.title}
      lede={problemCopy.lede}
    >
      <div className="grid gap-6 lg:grid-cols-2">
        {pains.map((pain) => (
          <article
            key={pain.title}
            data-reveal
            className={cn(
              "group rounded-2xl border bg-card p-8 transition-all duration-300",
              "hover:-translate-y-1 hover:border-destructive/20 hover:shadow-elevation-2 motion-reduce:hover:translate-y-0",
            )}
          >
            <div className="flex items-start gap-4">
              <span className="icon-tile bg-destructive/10 text-destructive">
                <pain.icon className="size-5" aria-hidden />
              </span>
              <div>
                <h3 className="font-semibold">{pain.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                  {pain.description}
                </p>
              </div>
            </div>
            <div
              aria-hidden="true"
              className="mt-6 rounded-xl border border-dashed bg-muted/40 p-4"
            >
              <Vignette kind={pain.vignette} />
            </div>
          </article>
        ))}
      </div>

      {/* Closing: metric chain -> emotional peak -> story-specific CTA. */}
      <div
        data-reveal
        className="mt-6 rounded-2xl border border-dashed bg-muted/40 px-6 py-8 text-center"
      >
        <ol className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
          {statusQuoChain.map((item, index) => (
            <li key={item} className="flex items-center gap-3">
              <span className="font-mono text-sm font-semibold text-destructive">
                {item}
              </span>
              {index < statusQuoChain.length - 1 ? (
                <ArrowRight
                  className="size-4 text-muted-foreground/60"
                  aria-hidden
                />
              ) : null}
            </li>
          ))}
        </ol>
        <p className="mx-auto mt-5 max-w-xl text-balance text-xl font-semibold tracking-tight">
          {problemClosing.statement}{" "}
          <span className="text-muted-foreground">{problemClosing.counter}</span>
        </p>
        <a
          href="#workflow"
          className="group mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-primary"
        >
          {problemClosing.cta}
          <ArrowRight
            className="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none"
            aria-hidden
          />
        </a>
      </div>
    </SectionShell>
  );
}
