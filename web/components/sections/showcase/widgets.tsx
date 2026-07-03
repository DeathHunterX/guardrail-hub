import { Lightbulb, Play } from "lucide-react";

import { StatusDot } from "@/components/shared/status-dot";
import { Badge } from "@/components/ui/badge";

import { dashboard, type DashboardFinding } from "./showcase.data";

const RADIAL_CIRCUMFERENCE = 2 * Math.PI * 30;

/** Widget shells are decorative mock-UI; the section copy carries semantics. */

export function ScoreRadial() {
  return (
    <div data-widget className="flex items-center gap-4 rounded-xl border bg-background/60 p-4">
      <svg viewBox="0 0 72 72" className="size-16 shrink-0 -rotate-90">
        <circle cx="36" cy="36" r="30" fill="none" strokeWidth="6" className="stroke-muted" />
        <circle
          data-radial-ring
          cx="36"
          cy="36"
          r="30"
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          className="stroke-success"
          strokeDasharray={RADIAL_CIRCUMFERENCE}
          strokeDashoffset={RADIAL_CIRCUMFERENCE * (1 - dashboard.score / 100)}
        />
      </svg>
      <div>
        <p className="text-xs text-muted-foreground">Security Score</p>
        <p data-score className="font-mono text-2xl font-semibold tabular-nums">
          {dashboard.score}
        </p>
        <p className="text-xs text-success">{dashboard.scoreDelta}</p>
      </div>
    </div>
  );
}

export function TrendChart() {
  const max = Math.max(...dashboard.trend);
  const points = dashboard.trend
    .map((value, index) => {
      const x = (index / (dashboard.trend.length - 1)) * 200;
      const y = 48 - (value / max) * 40;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <div data-widget className="rounded-xl border bg-background/60 p-4">
      <p className="text-xs text-muted-foreground">Vulnerability Trend · 30d</p>
      <svg viewBox="0 0 200 52" className="mt-2 h-14 w-full" aria-hidden="true">
        <polyline
          data-trend-path
          points={points}
          fill="none"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="stroke-primary"
        />
        <polygon
          points={`0,52 ${points} 200,52`}
          className="fill-primary/10"
        />
      </svg>
      <p className="text-xs text-success">↓ 74% open criticals this quarter</p>
    </div>
  );
}

export function ComplianceRings() {
  return (
    <div data-widget className="rounded-xl border bg-background/60 p-4">
      <p className="text-xs text-muted-foreground">Compliance Status</p>
      <ul className="mt-3 space-y-2.5">
        {dashboard.compliance.map((item) => (
          <li key={item.framework} className="flex items-center gap-3 text-xs">
            <span className="w-24 shrink-0 truncate">{item.framework}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <span
                data-compliance-bar
                className="block h-full origin-left rounded-full bg-primary"
                style={{ width: `${item.value}%` }}
              />
            </span>
            <span className="w-9 shrink-0 text-right font-mono text-muted-foreground">
              {item.label}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function severityOf(finding: DashboardFinding) {
  return finding.severity as "destructive" | "warning" | "neutral";
}

export function FindingsTable({ expanded = false }: { expanded?: boolean }) {
  const rows = expanded ? dashboard.findings : dashboard.findings.slice(0, 4);
  return (
    <div data-widget className="overflow-hidden rounded-xl border bg-background/60">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th scope="col" className="px-3 py-2 font-medium">Finding</th>
            <th scope="col" className="hidden px-3 py-2 font-medium sm:table-cell">Asset</th>
            <th scope="col" className="hidden px-3 py-2 font-medium md:table-cell">Scanner</th>
            <th scope="col" className="px-3 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((finding) => (
            <tr key={finding.title} data-table-row className="border-b last:border-0">
              <td className="flex items-center gap-2 px-3 py-2">
                <StatusDot status={severityOf(finding)} />
                <span className="truncate font-medium">{finding.title}</span>
              </td>
              <td className="hidden truncate px-3 py-2 font-mono text-muted-foreground sm:table-cell">
                {finding.asset}
              </td>
              <td className="hidden px-3 py-2 md:table-cell">
                <Badge variant="outline" className="px-1.5 text-[10px]">
                  {finding.scanner}
                </Badge>
              </td>
              <td className="px-3 py-2">
                <Badge
                  variant={
                    finding.status === "Fixed"
                      ? "success"
                      : finding.status === "Triaged"
                        ? "warning"
                        : "secondary"
                  }
                  className="px-1.5 text-[10px]"
                >
                  {finding.status}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AIRecommendations() {
  return (
    <div data-widget className="rounded-xl border bg-background/60 p-4">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Lightbulb className="size-3.5 text-warning" /> AI Recommendations
      </p>
      <ul className="mt-3 space-y-2.5">
        {dashboard.recommendations.map((rec) => (
          <li key={rec.title} className="rounded-lg border bg-card p-2.5">
            <p className="text-xs font-medium">{rec.title}</p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">{rec.detail}</p>
            <span className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-primary">
              <Play className="size-3" /> Apply fix
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ExecutionTimeline() {
  return (
    <div data-widget className="rounded-xl border bg-background/60 p-4">
      <p className="text-xs text-muted-foreground">Execution Timeline</p>
      <div className="mt-3 flex h-2 gap-0.5 overflow-hidden rounded-full">
        {dashboard.timeline.map((stage, index) => (
          <span
            key={stage.stage}
            data-timeline-bar
            className="h-full origin-left rounded-sm bg-primary"
            style={{ width: `${stage.width}%`, opacity: 1 - index * 0.15 }}
          />
        ))}
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
        <span>{dashboard.timeline[0]?.stage}</span>
        <span>{dashboard.timeline[dashboard.timeline.length - 1]?.stage}</span>
      </div>
    </div>
  );
}

export function LiveLogs({ tall = false }: { tall?: boolean }) {
  return (
    <div data-widget className="rounded-xl border bg-background/60 p-4">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <StatusDot status="success" pulse /> Live Logs
      </p>
      <div className={tall ? "mt-2 h-40 overflow-hidden" : "mt-2 h-24 overflow-hidden"}>
        <ul data-log-track className="space-y-1 font-mono text-[10px] leading-relaxed text-muted-foreground">
          {dashboard.logs.map((line) => (
            <li key={line} className="truncate">{line}</li>
          ))}
          {dashboard.logs.map((line) => (
            <li key={`${line}-loop`} aria-hidden="true" className="truncate">
              {line}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
