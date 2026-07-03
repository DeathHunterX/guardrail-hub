"use client";

import { useRef } from "react";

import { GlassPanel } from "@/components/shared/glass-panel";
import { useMotion } from "@/lib/gsap/gsap-provider";
import { durations, eases, revealStart, staggers } from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";
import { cn } from "@/lib/utils";

import { nodes, outputs, stages, type WorkflowNode } from "./workflow.data";

const STAGE_ORDER = stages.map((stage) => stage.id);

function stageNodes(stage: WorkflowNode["stage"]) {
  return nodes.filter((node) => node.stage === stage);
}

function NodeCard({ node, hub = false }: { node: WorkflowNode; hub?: boolean }) {
  return (
    <GlassPanel
      elevation={hub ? 3 : 1}
      className={cn(
        "flex items-center gap-3 p-3 transition-shadow",
        hub && "border-primary/40 p-4",
      )}
    >
      <span
        className={cn(
          "icon-tile size-9 rounded-md",
          hub && "size-11 rounded-lg bg-brand-gradient text-white",
        )}
      >
        <node.icon className={cn("size-4", hub && "size-5")} aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium">{node.label}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {node.role}
        </span>
      </span>
    </GlassPanel>
  );
}

/** Energy-flow connector: gradient sweep loops while the stage is active. */
function Connector() {
  return (
    <span
      data-connector
      aria-hidden="true"
      className="relative mx-auto block h-8 w-px shrink-0 overflow-hidden rounded-full bg-border lg:mx-0 lg:h-px lg:w-auto lg:flex-1"
    >
      <span
        data-connector-flow
        className="absolute inset-0 bg-gradient-to-b from-transparent via-primary to-transparent bg-[length:100%_300%] opacity-0 lg:bg-gradient-to-r lg:bg-[length:300%_100%]"
      />
    </span>
  );
}

/**
 * The validation pipeline stage (spec §6). Desktop ("full" tier): pinned and
 * scroll-scrubbed through six labeled chapters. Compact tier: one-shot play.
 * Initial dim states are applied via gsap.set + .to() tweens, the
 * refresh-proof pattern — nodes can never get stuck half-faded.
 */
export function NodeGraph() {
  const scope = useRef<HTMLDivElement>(null);
  const { tier } = useMotion();

  useGSAP(
    () => {
      if (tier === "none" || !scope.current) return;
      const q = gsap.utils.selector(scope.current);
      const captionEl =
        scope.current.querySelector<HTMLElement>("[data-stage-caption]");
      const railDots = q("[data-rail-dot]");

      const setStage = (index: number) => {
        const stage = stages[index];
        if (!stage) return;
        if (captionEl) captionEl.textContent = stage.caption;
        railDots.forEach((dot, dotIndex) =>
          dot.setAttribute("data-active", String(dotIndex <= index)),
        );
      };

      // Refresh-proof initial state.
      STAGE_ORDER.forEach((stageId) => {
        gsap.set(q(`[data-stage-group="${stageId}"]`), {
          autoAlpha: 0.25,
          scale: 0.94,
        });
      });

      const tl = gsap.timeline({
        defaults: { ease: eases.enter },
        scrollTrigger:
          tier === "full"
            ? {
                trigger: scope.current,
                pin: true,
                scrub: 0.8,
                start: "top top",
                end: "+=160%",
              }
            : { trigger: scope.current, start: revealStart, once: true },
      });

      STAGE_ORDER.forEach((stageId, index) => {
        const group = q(`[data-stage-group="${stageId}"]`);
        tl.addLabel(stageId);
        tl.call(setStage, [index]);
        tl.to(group, {
          autoAlpha: 1,
          scale: 1,
          duration: durations.md,
          stagger: staggers.tight,
        });
        const connector = q("[data-connector-flow]")[index];
        if (connector) {
          tl.to(connector, { opacity: 1, duration: durations.sm }, ">-0.2");
        }
        // Narrative dwell time per chapter while scrubbing.
        tl.to({}, { duration: 0.35 });
      });

      // Continuous energy flow along illuminated connectors, paused off-screen.
      const flows = gsap.to(q("[data-connector-flow]"), {
        backgroundPosition: "-200% -200%",
        duration: 2.4,
        ease: eases.linear,
        repeat: -1,
        paused: true,
      });
      const hub = scope.current.querySelector("[data-agent-hub]");
      const breathe = hub
        ? gsap.to(hub, {
            scale: 1.03,
            duration: 2.6,
            ease: "sine.inOut",
            yoyo: true,
            repeat: -1,
            paused: true,
          })
        : null;
      gsap.timeline({
        scrollTrigger: {
          trigger: scope.current,
          start: "top bottom",
          end: "bottom top",
          onToggle: (self) => {
            if (self.isActive) {
              flows.play();
              breathe?.play();
            } else {
              flows.pause();
              breathe?.pause();
            }
          },
        },
      });
    },
    { scope, dependencies: [tier] },
  );

  return (
    <div
      ref={scope}
      aria-hidden="true"
      className="pt-2 lg:flex lg:min-h-[88vh] lg:flex-col lg:justify-center"
    >
      <div className="flex flex-col items-stretch gap-2 lg:flex-row lg:items-center lg:gap-3">
        <div data-stage-group="ask" className="lg:w-44 lg:shrink-0">
          {stageNodes("ask").map((node) => (
            <NodeCard key={node.id} node={node} />
          ))}
        </div>
        <Connector />
        <div
          data-stage-group="orchestrate"
          data-agent-hub
          className="lg:w-52 lg:shrink-0"
        >
          {stageNodes("orchestrate").map((node) => (
            <NodeCard key={node.id} node={node} hub />
          ))}
        </div>
        <Connector />
        <div
          data-stage-group="scan"
          className="grid grid-cols-2 gap-2 lg:w-60 lg:shrink-0"
        >
          {stageNodes("scan").map((node) => (
            <GlassPanel
              key={node.id}
              elevation={1}
              className={cn(
                "flex items-center gap-2 p-2.5",
                node.id === "more" && "col-span-2 border-dashed",
              )}
            >
              <node.icon className="size-4 shrink-0 text-primary" aria-hidden />
              <span className="min-w-0">
                <span className="block truncate text-xs font-medium">
                  {node.label}
                </span>
                <span className="block truncate text-[10px] text-muted-foreground">
                  {node.role}
                </span>
              </span>
            </GlassPanel>
          ))}
        </div>
        <Connector />
        <div data-stage-group="validate" className="lg:w-48 lg:shrink-0">
          {stageNodes("validate").map((node) => (
            <NodeCard key={node.id} node={node} />
          ))}
        </div>
        <Connector />
        <div className="flex flex-col gap-2 lg:w-60 lg:shrink-0">
          <div data-stage-group="report" className="flex flex-col gap-2">
            {stageNodes("report").map((node) => (
              <NodeCard key={node.id} node={node} />
            ))}
            {/* Native tool outputs attached to the report. */}
            <div className="grid grid-cols-2 gap-2">
              {outputs.map((output) => (
                <GlassPanel
                  key={output.id}
                  elevation={1}
                  className="flex items-center gap-2 p-2.5"
                >
                  <output.icon
                    className="size-4 shrink-0 text-primary"
                    aria-hidden
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-medium">
                      {output.label}
                    </span>
                    <span className="block truncate text-[10px] text-muted-foreground">
                      {output.role}
                    </span>
                  </span>
                </GlassPanel>
              ))}
            </div>
          </div>
          <div data-stage-group="fix">
            {stageNodes("fix").map((node) => (
              <NodeCard key={node.id} node={node} />
            ))}
          </div>
        </div>
      </div>

      {/* Stage rail + live caption. */}
      <div className="mt-8 flex flex-col items-center gap-3 lg:mt-10">
        <ol className="flex items-center gap-2">
          {stages.map((stage) => (
            <li key={stage.id} className="flex items-center gap-2">
              <span
                data-rail-dot
                data-active="true"
                className="size-2 rounded-full bg-border transition-colors duration-300 data-[active=true]:bg-primary"
              />
            </li>
          ))}
        </ol>
        <p
          data-stage-caption
          className="min-h-10 max-w-md text-center text-sm text-muted-foreground"
        >
          {stages[stages.length - 1]?.caption}
        </p>
      </div>
    </div>
  );
}
