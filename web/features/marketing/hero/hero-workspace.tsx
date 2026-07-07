"use client";

import { Bot, Check, FileText, Play, Share2 } from "lucide-react";
import { useRef, useState } from "react";

import { GlassPanel } from "@/components/effects/glass-panel";
import { StatusDot } from "@/components/common/status-dot";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMotion } from "@/providers/gsap-provider";
import {
  durations,
  eases,
  introStartAfterLoad,
  shouldPlayIntro,
  staggers,
} from "@/lib/gsap/motion";
import { gsap, ScrollTrigger, useGSAP } from "@/lib/gsap/register";
import { cn } from "@/lib/utils";

import { demoScript } from "./data";

const SCORE_CIRCUMFERENCE = 2 * Math.PI * 34;
const TYPING_CHARS_PER_SECOND = 30;

/**
 * The live AI workspace (spec §3). SSR renders the completed state and it
 * stays visible after load; a fixed beat later (~3.2s, see
 * `introStartAfterLoad`) the master timeline resets the scene and replays
 * the story. On late hydration or restored scroll the intro is skipped
 * entirely. All dynamic sets live inside the timeline so Replay restarts
 * cleanly in every case.
 */
export function HeroWorkspace() {
  const scope = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<gsap.core.Timeline | null>(null);
  const [finished, setFinished] = useState(false);
  const { tier, entranceDone } = useMotion();
  // Decide once at mount: after late hydration or a restored scroll the
  // completed SSR state has already been on screen — zeroing it to replay
  // the story reads as freeze-blank-reload, so we keep the final state.
  const playIntro = useRef(shouldPlayIntro());

  // Static tiers and skipped intros keep the completed SSR state. When the
  // intro does play, the finished state intentionally stays visible until
  // the delayed story start — no reset happens at mount anymore.
  useGSAP(
    () => {
      if (!scope.current) return;
      if (tier === "none" || !playIntro.current) {
        setFinished(true);
      }
    },
    { scope, dependencies: [tier] },
  );

  useGSAP(
    () => {
      if (tier === "none" || !entranceDone || !scope.current) return;
      const root = scope.current;
      const q = gsap.utils.selector(root);

      const replyEl = root.querySelector<HTMLElement>("[data-chat-reply]");
      const bar = root.querySelector<HTMLElement>("[data-scan-bar]");
      const label = root.querySelector<HTMLElement>("[data-scan-label]");
      const ring = root.querySelector<SVGCircleElement>("[data-score-ring]");
      const scoreLabel = root.querySelector<HTMLElement>("[data-score-value]");
      const fullReply = demoScript.agentReply;
      const rootStyle = getComputedStyle(document.documentElement);
      const warningColor = `hsl(${rootStyle.getPropertyValue("--warning")})`;
      const successColor = `hsl(${rootStyle.getPropertyValue("--success")})`;

      const tl = gsap.timeline({
        defaults: { ease: eases.enter },
        paused: true,
        onComplete: () => setFinished(true),
      });
      timelineRef.current = tl;

      // 0. Reset (inside the timeline so Replay restarts from a clean state).
      // `immediateRender: false` keeps the completed SSR state visible while
      // the paused timeline waits for its delayed start.
      tl.set(q("[data-panel]"), {
        y: 40,
        autoAlpha: 0,
        immediateRender: false,
      });
      tl.set(q("[data-finding-row], [data-report-card], [data-log-line]"), {
        autoAlpha: 0,
        immediateRender: false,
      });
      tl.set(q("[data-tool-chip]"), {
        attr: { "data-state": "queued" },
        immediateRender: false,
      });
      tl.set(q("[data-scan-shimmer]"), {
        xPercent: -140,
        autoAlpha: 0,
        immediateRender: false,
      });
      if (ring) {
        tl.set(ring, {
          strokeDashoffset: SCORE_CIRCUMFERENCE,
          stroke: warningColor,
          immediateRender: false,
        });
      }
      tl.call(() => {
        if (replyEl) replyEl.textContent = "";
        if (bar) bar.style.transform = "scaleX(0)";
        if (label) label.textContent = "Preparing…";
        if (scoreLabel) scoreLabel.textContent = "0";
      });

      // 1. Panels land, back to front.
      tl.to(q("[data-panel]"), {
        y: 0,
        autoAlpha: 1,
        duration: durations.lg,
        ease: eases.land,
        stagger: staggers.loose,
      });

      // 2. Chat: user message pops, agent reply types out. Meanwhile the
      // scan bar shows an indeterminate "preparing" shimmer so the panel
      // never looks idle while tools spin up.
      tl.fromTo(
        q("[data-chat-user]"),
        { scale: 0.9, autoAlpha: 0 },
        { scale: 1, autoAlpha: 1, duration: durations.sm, ease: eases.pop },
        "-=0.4",
      );
      tl.addLabel("typing");
      tl.fromTo(
        q("[data-scan-shimmer]"),
        { xPercent: -140, autoAlpha: 1 },
        {
          xPercent: 340,
          duration: 1.2,
          ease: "power1.inOut",
          repeat: 4,
        },
        "typing",
      );
      if (replyEl) {
        const typing = { chars: 0 };
        tl.to(
          typing,
          {
            chars: fullReply.length,
            duration: fullReply.length / TYPING_CHARS_PER_SECOND,
            ease: eases.linear,
            onUpdate: () => {
              replyEl.textContent = fullReply.slice(0, Math.round(typing.chars));
            },
          },
          "typing",
        );
      }

      // 3. Tool chips flip queued -> running -> done in sequence.
      q("[data-tool-chip]").forEach((chip, index) => {
        tl.to(
          chip,
          {
            keyframes: [
              { scale: 1.08, duration: durations.xs },
              { scale: 1, duration: durations.xs },
            ],
            onStart: () => chip.setAttribute("data-state", "running"),
            onComplete: () => chip.setAttribute("data-state", "done"),
          },
          index === 0 ? "typing+=0.6" : ">0.1",
        );
      });

      // 4. Real scan progress takes over from the shimmer.
      tl.addLabel("scan");
      tl.set(q("[data-scan-shimmer]"), { autoAlpha: 0 }, "scan");
      const progress = { value: 0 };
      tl.to(
        progress,
        {
          value: 100,
          duration: 2.4,
          ease: "power1.inOut",
          onUpdate: () => {
            if (bar) bar.style.transform = `scaleX(${progress.value / 100})`;
            if (label) label.textContent = `${Math.round(progress.value)}%`;
          },
        },
        "scan",
      );
      tl.to(
        q("[data-log-line]"),
        { autoAlpha: 1, y: 0, duration: durations.sm, stagger: 0.35 },
        "scan",
      );

      // 5. Score gauge sweeps 0 -> 87, amber to green.
      if (ring && scoreLabel) {
        const score = { value: 0 };
        tl.to(
          ring,
          {
            strokeDashoffset:
              SCORE_CIRCUMFERENCE * (1 - demoScript.score / 100),
            stroke: successColor,
            duration: 1.6,
            ease: "power2.inOut",
          },
          "scan+=1.2",
        );
        tl.to(
          score,
          {
            value: demoScript.score,
            duration: 1.6,
            ease: "power2.inOut",
            onUpdate: () => {
              scoreLabel.textContent = String(Math.round(score.value));
            },
          },
          "scan+=1.2",
        );
      }

      // 6. Findings slide in one by one.
      tl.fromTo(
        q("[data-finding-row]"),
        { x: 24, autoAlpha: 0 },
        { x: 0, autoAlpha: 1, duration: durations.sm, stagger: 0.35 },
        ">-0.6",
      );

      // 7. Report card completes the story.
      tl.fromTo(
        q("[data-report-card]"),
        { scale: 0.9, autoAlpha: 0 },
        {
          scale: 1,
          autoAlpha: 1,
          duration: durations.md,
          ease: eases.pop,
        },
      );

      // Ambient: gentle float on panels, paused while off-screen.
      const floats = q("[data-panel]").map((panel, index) =>
        gsap.to(panel, {
          y: index % 2 === 0 ? -6 : 6,
          duration: 3 + index * 0.4,
          ease: "sine.inOut",
          yoyo: true,
          repeat: -1,
          paused: true,
        }),
      );
      ScrollTrigger.create({
        trigger: root,
        start: "top bottom",
        end: "bottom top",
        onToggle: (self) =>
          floats.forEach((f) => (self.isActive ? f.play() : f.pause())),
      });

      if (playIntro.current) {
        // The story starts a fixed beat (~3.2s) after page load: after a
        // refresh the completed state stays readable for a moment, then
        // the demo resets and plays — predictably, not mid-hydration.
        const delay = Math.max(
          0,
          introStartAfterLoad - performance.now() / 1000,
        );
        gsap.delayedCall(delay, () => tl.play());
      } else {
        // Intro skipped: park the fully built timeline at its end so the
        // visible state stays identical to the SSR markup, while the Replay
        // button can still restart the story from a clean zero state.
        tl.progress(1).pause();
      }
    },
    { scope, dependencies: [tier, entranceDone] },
  );

  const replay = () => {
    setFinished(false);
    timelineRef.current?.restart();
  };

  return (
    <div
      ref={scope}
      role="img"
      aria-label={`Animated demo: the Guardrail AI agent runs a scan on api.acme.dev, produces a security score of ${demoScript.score}, finds ${demoScript.findings.length} issues, and generates a compliance-mapped report.`}
      className="relative mx-auto h-[540px] w-full max-w-xl lg:max-w-none"
    >
      <div aria-hidden="true" className="size-full">
        {/* Chat panel — the anchor surface. */}
        <GlassPanel
          data-panel
          elevation={3}
          className="absolute left-0 top-0 w-[78%] p-4 sm:w-[70%]"
        >
          <div className="flex items-center gap-2 border-b pb-3">
            <span className="flex size-7 items-center justify-center rounded-full bg-brand-gradient text-white">
              <Bot className="size-4" />
            </span>
            <span className="text-sm font-medium">Guardrail Agent</span>
            <span className="ml-auto flex items-center gap-1.5 text-xs text-success">
              <StatusDot status="success" pulse /> online
            </span>
          </div>
          <div className="space-y-3 pt-3 text-sm">
            <p
              data-chat-user
              className="ml-auto w-fit max-w-[90%] rounded-xl rounded-br-sm bg-primary px-3 py-2 text-primary-foreground"
            >
              {demoScript.userMessage}
            </p>
            <p
              data-chat-reply
              className="min-h-16 w-fit max-w-[95%] rounded-xl rounded-bl-sm bg-muted px-3 py-2 text-muted-foreground"
            >
              {demoScript.agentReply}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {demoScript.tools.map((tool) => (
                <span
                  key={tool}
                  data-tool-chip
                  data-state="done"
                  className="group inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] data-[state=done]:border-success/40 data-[state=done]:text-success data-[state=queued]:text-muted-foreground data-[state=running]:text-primary"
                >
                  <Check className="size-3 group-data-[state=queued]:hidden group-data-[state=running]:hidden" />
                  {tool}
                </span>
              ))}
            </div>
          </div>
        </GlassPanel>

        {/* Scan progress + logs. */}
        <GlassPanel
          data-panel
          elevation={2}
          className="absolute right-0 top-[16%] w-[52%] p-4 sm:w-[46%]"
        >
          <div className="flex items-center justify-between text-xs font-medium">
            <span>Live scan</span>
            <span data-scan-label className="font-mono text-muted-foreground">
              100%
            </span>
          </div>
          <div className="relative mt-2 h-1.5 overflow-hidden rounded-full bg-primary/15">
            <div
              data-scan-bar
              className="h-full origin-left rounded-full bg-brand-gradient"
            />
            <span
              data-scan-shimmer
              className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-primary/40 opacity-0"
            />
          </div>
          <ul className="mt-3 space-y-1.5 font-mono text-[10px] leading-relaxed text-muted-foreground">
            {demoScript.logs.map((line) => (
              <li key={line} data-log-line className="truncate">
                <span className="text-success">›</span> {line}
              </li>
            ))}
          </ul>
        </GlassPanel>

        {/* Security score gauge — label centered inside the ring. */}
        <GlassPanel
          data-panel
          elevation={3}
          className="absolute bottom-[22%] left-[4%] w-40 p-4"
        >
          <div className="relative mx-auto size-[6.5rem]">
            <svg viewBox="0 0 80 80" className="size-full -rotate-90">
              <circle
                cx="40"
                cy="40"
                r="34"
                fill="none"
                strokeWidth="6"
                className="stroke-muted"
              />
              <circle
                data-score-ring
                cx="40"
                cy="40"
                r="34"
                fill="none"
                strokeWidth="6"
                strokeLinecap="round"
                className="stroke-success"
                strokeDasharray={SCORE_CIRCUMFERENCE}
                strokeDashoffset={
                  SCORE_CIRCUMFERENCE * (1 - demoScript.score / 100)
                }
              />
            </svg>
            <span className="absolute inset-0 flex flex-col items-center justify-center">
              <span
                data-score-value
                className="font-mono text-2xl font-semibold leading-none tabular-nums"
              >
                {demoScript.score}
              </span>
              <span className="mt-1 text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                Score
              </span>
            </span>
          </div>
        </GlassPanel>

        {/* Findings feed — hidden on the smallest screens (spec §3 responsive). */}
        <GlassPanel
          data-panel
          elevation={2}
          className="absolute bottom-[14%] right-[2%] hidden w-[56%] p-3 sm:block"
        >
          <p className="pb-2 text-xs font-medium">Findings</p>
          <ul className="space-y-1.5">
            {demoScript.findings.map((finding) => (
              <li
                key={finding.title}
                data-finding-row
                className="flex items-center gap-2 rounded-lg border bg-background/50 px-2.5 py-1.5 text-xs"
              >
                <StatusDot
                  status={finding.severity as "destructive" | "warning"}
                />
                <span className="truncate font-medium">{finding.title}</span>
                <span className="hidden truncate font-mono text-[10px] text-muted-foreground md:inline">
                  {finding.asset}
                </span>
                <Badge
                  variant={finding.severity as "destructive" | "warning"}
                  className="ml-auto shrink-0 px-1.5 text-[10px]"
                >
                  {finding.tag}
                </Badge>
              </li>
            ))}
          </ul>
        </GlassPanel>

        {/* Report card — the story's resolution. */}
        <GlassPanel
          data-panel
          data-report-card
          elevation={3}
          className="absolute bottom-0 left-[18%] flex w-[58%] items-center gap-3 p-4 sm:w-[46%]"
        >
          <span className="icon-tile">
            <FileText className="size-5" />
          </span>
          <span className="min-w-0 text-xs">
            <span className="block font-medium">Report ready</span>
            <span className="flex items-center gap-1 text-muted-foreground">
              <Check className="size-3 text-success" /> SOC 2 mapped · PDF
            </span>
          </span>
          <Share2 className="ml-auto size-4 shrink-0 text-muted-foreground" />
        </GlassPanel>
      </div>

      {finished && tier !== "none" ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={replay}
          className={cn(
            "absolute -bottom-10 right-0 text-muted-foreground",
            "hover:text-foreground",
          )}
        >
          <Play aria-hidden /> Replay
        </Button>
      ) : null}
    </div>
  );
}
