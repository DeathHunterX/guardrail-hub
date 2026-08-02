"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BarChart } from "@/components/common/bar-chart";
import { DashboardCard } from "@/components/common/dashboard-card";
import { DonutChart } from "@/components/common/donut-chart";
import { ErrorState } from "@/components/common/error-state";
import { LineChart } from "@/components/common/line-chart";
import { MetricCard } from "@/components/common/metric-card";
import { Button } from "@/components/ui/button";
import { useSession } from "@/hooks/use-session";
import { getDashboardOverview } from "@/services/dashboard.service";
import type { ServiceError } from "@/types/api";
import type { DashboardOverview } from "@/types/dashboard";

import { metricIcons, overviewCopy, quickActions } from "./data";
import {
  ActivityTimeline,
  OverviewSkeleton,
  RecentOperationsTable,
  RecentReportsList,
  SystemStatusList,
} from "./widgets";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ServiceError }
  | { status: "ready"; data: DashboardOverview };

export function Overview() {
  const { session } = useSession();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  // Canonical fetch-in-effect: state updates land asynchronously in the
  // promise callback and are ignored after unmount; `attempt` re-runs it.
  useEffect(() => {
    let cancelled = false;
    void getDashboardOverview().then((result) => {
      if (cancelled) return;
      setState(
        result.ok
          ? { status: "ready", data: result.data }
          : { status: "error", error: result.error },
      );
    });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = () => {
    setState({ status: "loading" });
    setAttempt((current) => current + 1);
  };

  if (state.status === "loading") return <OverviewSkeleton />;

  if (state.status === "error") {
    return (
      <ErrorState
        description={state.error.message}
        onRetry={retry}
        className="min-h-[50vh]"
      />
    );
  }

  const { data } = state;
  const firstName = session?.user.fullName.split(" ")[0] ?? "there";

  return (
    <div className="space-y-6">
      {/* Welcome + quick actions. */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[0.8125rem] font-medium uppercase tracking-widest text-muted-foreground">
            {overviewCopy.welcome.eyebrow}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight md:text-3xl">
            {overviewCopy.welcome.greeting.replace("{name}", firstName)}
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {overviewCopy.welcome.lede}
          </p>
        </div>
        <div
          role="group"
          aria-label={overviewCopy.quickActionsTitle}
          className="flex flex-wrap gap-2"
        >
          {quickActions.map((action, index) => (
            <Button
              key={action.label}
              variant={index === 0 ? "default" : "outline"}
              size="sm"
              className={index === 0 ? "btn-sheen" : undefined}
              asChild
            >
              <Link href={action.href}>
                <action.icon aria-hidden="true" />
                {action.label}
              </Link>
            </Button>
          ))}
        </div>
      </div>

      {/* KPI metrics. */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => (
          <MetricCard
            key={metric.id}
            label={metric.label}
            value={metric.value}
            delta={metric.delta}
            deltaTone={metric.deltaTone}
            icon={metricIcons[metric.id]}
          />
        ))}
      </div>

      {/* Operations + success rate. */}
      <div className="grid gap-4 lg:grid-cols-3">
        <DashboardCard
          title="Operations Timeline"
          description="Executions per day · last 7 days"
          className="lg:col-span-2"
        >
          <LineChart
            series={data.charts.operationsTimeline.series}
            labels={data.charts.operationsTimeline.labels}
            ariaLabel="Operations per day over the last 7 days, split by succeeded and failed"
          />
        </DashboardCard>
        <DashboardCard
          title="Execution Success Rate"
          description="Rolling 7-day window"
        >
          <DonutChart
            segments={data.charts.successRate.segments}
            centerValue={data.charts.successRate.centerValue}
            centerLabel="success"
            ariaLabel={`Execution success rate ${data.charts.successRate.centerValue} over the last 7 days`}
          />
        </DashboardCard>
      </div>

      {/* Findings, workers, performance. */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DashboardCard
          title="Findings Trend"
          description="Open findings by severity"
        >
          <LineChart
            series={data.charts.findingsTrend.series}
            labels={data.charts.findingsTrend.labels}
            area={false}
            ariaLabel="Open security findings by severity over the last 7 days, trending downward"
          />
        </DashboardCard>
        <DashboardCard
          title="Worker Utilization"
          description="Current load per worker"
        >
          <BarChart
            data={data.charts.workerUtilization}
            ariaLabel="Current utilization percentage per worker"
            formatValue={(value) => `${value}%`}
          />
        </DashboardCard>
        <DashboardCard
          title="Performance History"
          description="p95 latency across load tests"
          className="md:col-span-2 xl:col-span-1"
        >
          <LineChart
            series={data.charts.performanceHistory.series}
            labels={data.charts.performanceHistory.labels}
            ariaLabel="p95 latency in milliseconds across load tests over the last 7 days"
          />
        </DashboardCard>
      </div>

      {/* Recent operations + system status. */}
      <div className="grid gap-4 lg:grid-cols-3">
        <DashboardCard
          title="Recent Operations"
          description="Latest scans and load tests"
          className="lg:col-span-2"
          contentClassName="px-0 pb-2"
          action={
            <Button variant="ghost" size="sm" asChild>
              <Link href="/operations">View all</Link>
            </Button>
          }
        >
          <RecentOperationsTable operations={data.operations} />
        </DashboardCard>
        <DashboardCard
          title="System Status"
          description="Platform health at a glance"
          action={
            <Button variant="ghost" size="sm" asChild>
              <Link href="/help">Status page</Link>
            </Button>
          }
        >
          <SystemStatusList components={data.systemStatus} />
        </DashboardCard>
      </div>

      {/* Activity + reports. */}
      <div className="grid gap-4 lg:grid-cols-3">
        <DashboardCard
          title="Recent Activity"
          description="Team and agent actions"
          className="lg:col-span-2"
        >
          <ActivityTimeline events={data.activity} />
        </DashboardCard>
        <DashboardCard
          title="Recent Reports"
          description="Generated in the last 7 days"
          action={
            <Button variant="ghost" size="sm" asChild>
              <Link href="/reports">View all</Link>
            </Button>
          }
        >
          <RecentReportsList reports={data.reports} />
        </DashboardCard>
      </div>
    </div>
  );
}
