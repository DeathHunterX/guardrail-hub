import { Check, GitCommitHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { StatusDot } from "@/components/common/status-dot";

import { demoPrompts } from "./data";
import type { Feature } from "./types";

/**
 * Bento cell micro-visuals (spec §7): token-built mock-UI fragments with the
 * same visual grammar as the hero and dashboard. All decorative.
 */
export function FeatureVisual({ kind }: { kind: Feature["visual"] }) {
  switch (kind) {
    case "chat":
      return (
        <div className="space-y-2.5">
          {/* User request bubble. */}
          <p className="ml-auto w-fit rounded-lg rounded-br-sm bg-primary px-3 py-1.5 text-xs text-primary-foreground">
            {demoPrompts[0]}
          </p>
          {/* Agent reply: scoped plan in plain language. */}
          <p className="w-fit max-w-[95%] rounded-lg rounded-bl-sm bg-background px-3 py-1.5 text-xs text-muted-foreground">
            Scoping payment-api — 3 endpoints need auth coverage. Running DAST
            plus targeted E2E, read-only.
          </p>
          {/* Orchestrated toolbelt for this run. */}
          <div className="flex flex-wrap gap-1.5">
            {["ZAP", "Semgrep", "Trivy", "Playwright"].map((tool) => (
              <Badge key={tool} variant="outline" className="font-mono text-[10px]">
                {tool}
              </Badge>
            ))}
          </div>
          {/* Live run status lines. */}
          <ul className="space-y-1.5 text-xs text-muted-foreground">
            <li className="flex items-center gap-2">
              <StatusDot status="success" />
              <span className="font-mono">ZAP baseline — passed</span>
            </li>
            <li className="flex items-center gap-2">
              <StatusDot status="warning" />
              <span className="font-mono">Auth bypass probe — 1 finding</span>
            </li>
          </ul>
          <p className="flex items-center gap-1.5 pt-1 text-xs text-success">
            <Check className="size-3.5" /> Scan complete — 1 medium, fix PR
            drafted
          </p>
          {/* Follow-up suggestions the agent also understands. */}
          <div className="flex flex-wrap gap-1.5 border-t border-dashed pt-2.5">
            {demoPrompts.slice(1).map((prompt) => (
              <p
                key={prompt}
                className="w-fit rounded-lg border border-dashed px-3 py-1.5 text-xs text-muted-foreground"
              >
                {prompt}
              </p>
            ))}
          </div>
        </div>
      );
    case "commits":
      return (
        <div className="flex items-center gap-1.5">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className="flex items-center gap-1.5">
              <span className="flex size-6 items-center justify-center rounded-full border bg-background">
                <GitCommitHorizontal className="size-3 text-primary" />
              </span>
              {i < 3 ? <span className="h-px w-4 bg-border" /> : null}
            </span>
          ))}
          <Check className="ml-1 size-4 text-success" />
        </div>
      );
    case "dedupe":
      return (
        <div className="flex items-center gap-2 text-xs">
          <Badge variant="outline" className="font-mono line-through opacity-50">
            CVE-2026-4411 ×3
          </Badge>
          <span className="text-muted-foreground">→</span>
          <Badge variant="warning" className="font-mono">
            1 finding
          </Badge>
        </div>
      );
    case "checklist":
      return (
        <ul className="space-y-2 text-xs">
          {[
            ["OWASP A03: Injection", "success"],
            ["SOC 2 CC7.1", "success"],
            ["ISO 27001 A.12.6", "success"],
            ["PCI DSS 6.5.1", "warning"],
          ].map(([label, status]) => (
            <li key={label} className="flex items-center gap-2">
              <StatusDot status={status as "success" | "warning"} />
              <span className="font-mono text-muted-foreground">{label}</span>
            </li>
          ))}
        </ul>
      );
    case "diff":
      return (
        <pre className="font-mono text-[10px] leading-relaxed">
          <code>
            <span className="block rounded bg-destructive/10 px-1.5 text-destructive">
              - query(`SELECT * WHERE id=${"${id}"}`)
            </span>
            <span className="block rounded bg-success/10 px-1.5 text-success">
              + query(`SELECT * WHERE id=?`, [id])
            </span>
          </code>
        </pre>
      );
    case "pipeline":
      return (
        <div className="flex items-center gap-1.5">
          {["build", "test", "guardrail", "deploy"].map((step) => (
            <span
              key={step}
              className={
                step === "guardrail"
                  ? "rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-medium text-primary"
                  : "rounded-full border px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
              }
            >
              {step}
            </span>
          ))}
        </div>
      );
    case "report":
      return (
        <div className="flex items-end gap-3">
          <svg viewBox="0 0 120 32" className="h-8 w-28" aria-hidden="true">
            <polyline
              points="0,26 20,22 40,24 60,14 80,16 100,8 120,6"
              fill="none"
              strokeWidth="2"
              className="stroke-primary"
              strokeLinecap="round"
            />
          </svg>
          <Badge variant="secondary" className="text-[10px]">
            Export PDF
          </Badge>
        </div>
      );
    case "team":
      return (
        <div className="flex items-center gap-2">
          <span className="flex -space-x-2">
            {["AL", "MK", "TS"].map((initials) => (
              <span
                key={initials}
                className="flex size-6 items-center justify-center rounded-full border-2 border-card bg-primary/10 text-[9px] font-medium text-primary"
              >
                {initials}
              </span>
            ))}
          </span>
          <Badge variant="success" className="text-[10px]">
            SLA on track
          </Badge>
        </div>
      );
    case "secrets":
      return (
        <div className="space-y-2">
          <pre className="font-mono text-[10px] leading-relaxed">
            <code>
              <span className="block rounded bg-destructive/10 px-1.5 text-destructive">
                AWS_SECRET_KEY=&quot;AKIA••••••••••••&quot;
              </span>
            </code>
          </pre>
          <Badge variant="destructive" className="text-[10px]">
            Blocked at commit
          </Badge>
        </div>
      );
    case "audit":
      return (
        <ul className="space-y-1.5 font-mono text-[10px] leading-relaxed text-muted-foreground">
          <li>14:02:11 agent.scan.start — staging</li>
          <li>14:05:47 finding.assigned — @mk</li>
          <li>14:06:03 report.signed — sha256 ✓</li>
        </ul>
      );
  }
}
