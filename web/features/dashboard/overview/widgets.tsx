import { FileText, Inbox } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { MetricCardSkeleton } from "@/components/common/metric-card";
import { StatusDot } from "@/components/common/status-dot";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatRelativeTime } from "@/lib/utils";
import type {
  ActivityEvent,
  OperationRow,
  OperationStatus,
  ReportSummary,
  SystemComponentStatus,
} from "@/types/dashboard";

/* ------------------------------ operations ------------------------------ */

const operationStatusPresentation: Record<
  OperationStatus,
  {
    label: string;
    variant: "secondary" | "outline" | "success" | "destructive";
  }
> = {
  running: { label: "Running", variant: "secondary" },
  queued: { label: "Queued", variant: "outline" },
  succeeded: { label: "Succeeded", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
};

export function RecentOperationsTable({
  operations,
}: {
  operations: OperationRow[];
}) {
  if (operations.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="No operations yet"
        description="Scans and load tests will appear here as soon as one starts."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Operation</TableHead>
          <TableHead className="hidden sm:table-cell">Project</TableHead>
          <TableHead className="hidden md:table-cell">Engine</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="hidden text-right sm:table-cell">
            Duration
          </TableHead>
          <TableHead className="hidden text-right lg:table-cell">
            Started
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {operations.map((operation) => {
          const status = operationStatusPresentation[operation.status];
          return (
            <TableRow key={operation.id}>
              <TableCell className="font-medium">
                <span className="flex items-center gap-2">
                  {operation.status === "running" ? (
                    <StatusDot status="success" pulse />
                  ) : null}
                  <span className="truncate">{operation.name}</span>
                </span>
              </TableCell>
              <TableCell className="hidden truncate font-mono text-xs text-muted-foreground sm:table-cell">
                {operation.project}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                <Badge variant="outline" className="px-1.5 text-[10px]">
                  {operation.engine}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge variant={status.variant} className="px-1.5 text-[10px]">
                  {status.label}
                </Badge>
              </TableCell>
              <TableCell className="hidden text-right font-mono text-xs tabular-nums text-muted-foreground sm:table-cell">
                {operation.duration}
              </TableCell>
              <TableCell className="hidden text-right text-xs text-muted-foreground lg:table-cell">
                {formatRelativeTime(operation.startedAt)}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

/* ------------------------------- activity ------------------------------- */

export function ActivityTimeline({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="No recent activity"
        description="Team and agent actions across your projects will show up here."
      />
    );
  }

  return (
    <ol className="relative space-y-5 before:absolute before:inset-y-1 before:left-[3px] before:w-px before:bg-border">
      {events.map((event) => (
        <li key={event.id} className="relative flex gap-3 pl-5">
          <StatusDot
            status={event.tone === "neutral" ? "neutral" : event.tone}
            className="absolute left-0 top-1.5"
          />
          <div className="min-w-0 flex-1">
            <p className="text-sm leading-snug">
              <span className="font-medium">{event.actor}</span>{" "}
              <span className="text-muted-foreground">{event.action}</span>{" "}
              <span className="font-medium">{event.target}</span>
            </p>
            <time className="mt-0.5 block text-xs text-muted-foreground">
              {formatRelativeTime(event.at)}
            </time>
          </div>
        </li>
      ))}
    </ol>
  );
}

/* ----------------------------- system status ---------------------------- */

const systemStatusPresentation: Record<
  SystemComponentStatus["status"],
  { label: string; dot: "success" | "warning" | "destructive" }
> = {
  operational: { label: "Operational", dot: "success" },
  degraded: { label: "Degraded", dot: "warning" },
  outage: { label: "Outage", dot: "destructive" },
};

export function SystemStatusList({
  components,
}: {
  components: SystemComponentStatus[];
}) {
  return (
    <ul className="space-y-3">
      {components.map((component) => {
        const status = systemStatusPresentation[component.status];
        return (
          <li key={component.id} className="flex items-center gap-3">
            <StatusDot
              status={status.dot}
              pulse={component.status !== "operational"}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{component.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {component.detail}
              </p>
            </div>
            <span className="shrink-0 text-xs text-muted-foreground">
              {status.label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------- reports -------------------------------- */

export function RecentReportsList({ reports }: { reports: ReportSummary[] }) {
  if (reports.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="No reports yet"
        description="Generated security, performance, and compliance reports land here."
      />
    );
  }

  return (
    <ul className="space-y-1">
      {reports.map((report) => (
        <li key={report.id}>
          <Link
            href="/reports"
            className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-accent/60"
          >
            <span className="icon-tile size-8 rounded-md">
              <FileText className="size-4" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {report.name}
              </span>
              <span className="block text-xs text-muted-foreground">
                {report.kind} · {formatRelativeTime(report.generatedAt)}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------- skeleton ------------------------------- */

/** Full-page loading placeholder mirroring the overview's real layout. */
export function OverviewSkeleton() {
  return (
    <div aria-hidden="true" className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <MetricCardSkeleton key={index} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-4 h-40 w-full" />
        </Card>
        <Card className="p-6">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="mt-4 h-40 w-full" />
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <Skeleton className="h-4 w-36" />
          <div className="mt-4 space-y-3">
            {Array.from({ length: 5 }, (_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        </Card>
        <Card className="p-6">
          <Skeleton className="h-4 w-28" />
          <div className="mt-4 space-y-3">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
