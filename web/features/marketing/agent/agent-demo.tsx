"use client";

import { ArrowRight, Bot } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { StatusDot } from "@/components/common/status-dot";
import { Badge } from "@/components/ui/badge";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { siteConfig } from "@/config/site";
import { useMotion } from "@/providers/gsap-provider";
import { durations, eases, staggers } from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";

import { scenarios } from "./data";
import type { Scenario } from "./types";

function ScenarioBlocks({ scenario }: { scenario: Scenario }) {
  return (
    <>
      <p
        data-agent-block
        className="ml-auto w-fit max-w-[85%] rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground"
      >
        {scenario.user}
      </p>
      {scenario.blocks.map((block, index) => {
        if (block.type === "text") {
          return (
            <p
              key={index}
              data-agent-block
              className="w-fit max-w-[92%] rounded-xl rounded-bl-sm bg-muted px-3 py-2 text-sm text-muted-foreground"
            >
              {block.text}
            </p>
          );
        }
        if (block.type === "tools") {
          return (
            <div key={index} data-agent-block className="flex flex-wrap gap-1.5">
              {block.tools?.map((tool) => (
                <Badge key={tool} variant="outline" className="font-mono text-[10px]">
                  {tool}
                </Badge>
              ))}
            </div>
          );
        }
        if (block.type === "table") {
          return (
            <ul
              key={index}
              data-agent-block
              className="w-full max-w-[92%] divide-y rounded-xl border bg-background/60 text-xs"
            >
              {block.rows?.map((row) => (
                <li key={row.label} className="flex items-center justify-between px-3 py-1.5">
                  <span className="font-mono">{row.label}</span>
                  <span
                    className={
                      row.value.includes("exposed")
                        ? "font-medium text-warning"
                        : "text-muted-foreground"
                    }
                  >
                    {row.value}
                  </span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <div key={index} data-agent-block>
            <Badge variant={block.badge?.variant ?? "success"}>
              {block.badge?.label}
            </Badge>
          </div>
        );
      })}
    </>
  );
}

/**
 * Interactive agent demo (spec §9): eight canned scenarios selectable via
 * chips. Completed replies are real DOM text (content, not decoration);
 * the motion is presentation-only, so find-in-page and screen readers get
 * the full text instantly.
 */
export function AgentDemo() {
  const scope = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<string>(scenarios[0]?.id ?? "staging");
  const { tier } = useMotion();

  const scenario =
    scenarios.find((item) => item.id === active) ?? scenarios[0]!;

  useGSAP(
    () => {
      if (tier === "none" || !scope.current) return;
      const blocks = scope.current.querySelectorAll("[data-agent-block]");
      gsap.from(blocks, {
        y: 14,
        autoAlpha: 0,
        duration: durations.sm,
        ease: eases.enter,
        stagger: staggers.loose * 2,
      });
    },
    { scope, dependencies: [tier, active] },
  );

  return (
    <div ref={scope} className="relative">
      <div
        aria-hidden="true"
        className="dot-grid-bg absolute -inset-4 -z-10 rounded-3xl opacity-60"
      />
      <ToggleGroup
        type="single"
        value={active}
        onValueChange={(value) => value && setActive(value)}
        aria-label="Example agent conversations"
        className="flex-wrap justify-start gap-2"
      >
        {scenarios.map((item) => (
          <ToggleGroupItem
            key={item.id}
            value={item.id}
            variant="outline"
            size="sm"
            className="rounded-full text-xs data-[state=on]:border-primary"
          >
            {item.chip}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      <div
        aria-label="Interactive demo conversation"
        className="mt-4 flex h-[420px] flex-col overflow-hidden rounded-2xl border bg-card shadow-elevation-2"
      >
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <span
            data-agent-avatar
            className="flex size-7 items-center justify-center rounded-full bg-brand-gradient text-white"
          >
            <Bot className="size-4" aria-hidden />
          </span>
          <span className="text-sm font-medium">Guardrail Agent</span>
          <span className="ml-auto flex items-center gap-1.5 text-xs text-success">
            <StatusDot status="success" pulse /> online
          </span>
        </div>
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
          <ScenarioBlocks scenario={scenario} />
        </div>
        {/* The demo converts: the "input" is a link to signup. */}
        <Link
          href={siteConfig.app.signUp}
          className="group flex items-center gap-2 border-t px-4 py-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          Ask anything — try it free
          <ArrowRight
            className="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none"
            aria-hidden
          />
        </Link>
      </div>
    </div>
  );
}
