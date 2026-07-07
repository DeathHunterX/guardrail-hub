"use client";

import { useRef, useState } from "react";

import { MockWindow } from "@/components/effects/mock-window";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMotion } from "@/providers/gsap-provider";
import { durations, eases, staggers } from "@/lib/gsap/motion";
import { gsap, ScrollTrigger, useGSAP } from "@/lib/gsap/register";

import { dashboard, showcaseTabs } from "./data";
import {
  AIRecommendations,
  ComplianceRings,
  ExecutionTimeline,
  FindingsTable,
  LiveLogs,
  ScoreRadial,
  TrendChart,
} from "./widgets";

type TabId = (typeof showcaseTabs)[number]["id"];

/**
 * Dashboard showcase (spec §8). The window lands with a perspective flatten,
 * widgets populate in reading order, then ambient life takes over: the log
 * stream loops and the trend line stays drawn. Tab switches re-run the
 * populate cascade for the incoming layout.
 */
export function DashboardMock() {
  const scope = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const { tier } = useMotion();

  // Entrance: one-shot window landing.
  useGSAP(
    () => {
      if (tier === "none" || !scope.current) return;
      gsap.from(scope.current.querySelector("[data-window]"), {
        y: 80,
        scale: 0.95,
        rotationX: 6,
        transformPerspective: 900,
        autoAlpha: 0,
        duration: durations.xl,
        ease: eases.land,
        scrollTrigger: {
          trigger: scope.current,
          start: "top 75%",
          once: true,
        },
      });

      // Ambient: log stream loop, paused off-screen.
      const track = scope.current.querySelector("[data-log-track]");
      if (track) {
        const loop = gsap.to(track, {
          yPercent: -50,
          duration: 14,
          ease: eases.linear,
          repeat: -1,
          paused: true,
        });
        ScrollTrigger.create({
          trigger: scope.current,
          start: "top bottom",
          end: "bottom top",
          onToggle: (self) => (self.isActive ? loop.play() : loop.pause()),
        });
      }
    },
    { scope, dependencies: [tier] },
  );

  // Widget cascade on every tab layout change.
  useGSAP(
    () => {
      if (tier === "none" || !scope.current) return;
      gsap.from(scope.current.querySelectorAll("[data-widget]"), {
        y: 16,
        autoAlpha: 0,
        duration: durations.sm,
        ease: eases.enter,
        stagger: staggers.tight,
      });
      gsap.from(scope.current.querySelectorAll("[data-table-row]"), {
        x: 12,
        autoAlpha: 0,
        duration: durations.sm,
        ease: eases.enter,
        stagger: staggers.tight,
        delay: 0.1,
      });
    },
    { scope, dependencies: [tier, tab] },
  );

  return (
    <div ref={scope}>
      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value as TabId)}
        className="flex flex-col items-center"
      >
        <TabsList aria-label="Dashboard views">
          {showcaseTabs.map((item) => (
            <TabsTrigger key={item.id} value={item.id}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div
        data-window
        role="img"
        aria-label={`Product dashboard preview: security score ${dashboard.score}, declining vulnerability trend, ${dashboard.findings.length} tracked findings, compliance coverage for OWASP, SOC 2 and ISO 27001, AI fix recommendations, and a live agent log.`}
        className="mt-6"
      >
        <MockWindow
          variant="browser"
          url="app.guardrailhub.com/acme/production"
          contentClassName="p-4 sm:p-6"
          className="mx-auto max-w-6xl"
        >
          <div aria-hidden="true" className="md:min-h-[560px]">
            {/* Mock top bar. */}
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">acme-platform</span>
              <Badge variant="secondary" className="font-mono text-[10px]">
                production
              </Badge>
              <span className="ml-auto rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground">
                Run scan
              </span>
            </div>

            {tab === "overview" ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <ScoreRadial />
                <TrendChart />
                <ComplianceRings />
                <div className="md:col-span-2 lg:col-span-3">
                  <FindingsTable />
                </div>
                <AIRecommendations />
                <ExecutionTimeline />
                <LiveLogs />
              </div>
            ) : null}
            {tab === "findings" ? (
              <div className="grid gap-4 lg:grid-cols-3">
                <div className="space-y-4 lg:col-span-2">
                  <FindingsTable expanded />
                  <TrendChart />
                </div>
                <div className="space-y-4">
                  <AIRecommendations />
                  <ExecutionTimeline />
                </div>
              </div>
            ) : null}
            {tab === "compliance" ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <ComplianceRings />
                <ScoreRadial />
                <TrendChart />
                <div className="md:col-span-2 lg:col-span-3">
                  <FindingsTable expanded />
                </div>
              </div>
            ) : null}
            {tab === "activity" ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-4">
                  <LiveLogs tall />
                  <ExecutionTimeline />
                </div>
                <div className="space-y-4">
                  <AIRecommendations />
                  <TrendChart />
                </div>
              </div>
            ) : null}
          </div>
        </MockWindow>
      </div>
    </div>
  );
}
