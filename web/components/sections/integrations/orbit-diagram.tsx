"use client";

import { Bot } from "lucide-react";
import { useRef } from "react";

import { useMotion } from "@/lib/gsap/gsap-provider";
import { eases } from "@/lib/gsap/motion";
import { gsap, ScrollTrigger, useGSAP } from "@/lib/gsap/register";

import { integrations } from "./integrations.data";

const INNER_RADIUS = 130;
const OUTER_RADIUS = 220;
const INNER_DURATION = 90;
const OUTER_DURATION = 140;

function OrbitBadges({
  ring,
  radius,
}: {
  ring: "inner" | "outer";
  radius: number;
}) {
  const items = integrations.filter((item) => item.ring === ring);
  return (
    <>
      {items.map((item, index) => {
        const angle = (index / items.length) * 360;
        return (
          /* Zero-size "arm": its transform-origin is a 0x0 point at the exact
             diagram center, so rotate + translateX lands on a true circle.
             A sized wrapper here would rotate around its own box center
             (which varies with label width) and scatter the radii. */
          <span
            key={item.name}
            className="absolute left-1/2 top-1/2 size-0"
            style={{
              transform: `rotate(${angle}deg) translateX(${radius}px)`,
            }}
          >
            {/* Centering layer: carries only the class translate (never an
               inline or GSAP transform), so the badge box stays centered on
               the orbit point regardless of its width. */}
            <span className="absolute left-0 top-0 block -translate-x-1/2 -translate-y-1/2">
              {/* Counter-rotation keeps labels upright while the ring spins;
                 GSAP animates this rotation relative to the start angle. */}
              <span
                data-orbit-badge={ring}
                style={{ transform: `rotate(${-angle}deg)` }}
                className="glass-surface flex items-center whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium shadow-elevation-2"
              >
                {item.name}
              </span>
            </span>
          </span>
        );
      })}
    </>
  );
}

/**
 * Orbit diagram (spec §10). Desktop-only theater — fully redundant with the
 * accessible grid below it, hence aria-hidden. Rings spin in opposite
 * directions; badges counter-rotate to stay readable; everything pauses
 * off-screen and never spins under reduced motion.
 */
export function OrbitDiagram() {
  const scope = useRef<HTMLDivElement>(null);
  const { tier } = useMotion();

  useGSAP(
    () => {
      if (tier !== "full" || !scope.current) return;
      const q = gsap.utils.selector(scope.current);

      const spins = [
        gsap.to(q("[data-ring='inner']"), {
          rotation: 360,
          duration: INNER_DURATION,
          ease: eases.linear,
          repeat: -1,
          paused: true,
        }),
        gsap.to(q("[data-ring='outer']"), {
          rotation: -360,
          duration: OUTER_DURATION,
          ease: eases.linear,
          repeat: -1,
          paused: true,
        }),
        // Badges counter-spin so text stays level. Relative values keep each
        // badge's own start angle intact; absolute targets would snap every
        // badge to the same rotation and desync them from the ring.
        gsap.to(q("[data-orbit-badge='inner']"), {
          rotation: "-=360",
          duration: INNER_DURATION,
          ease: eases.linear,
          repeat: -1,
          paused: true,
        }),
        gsap.to(q("[data-orbit-badge='outer']"), {
          rotation: "+=360",
          duration: OUTER_DURATION,
          ease: eases.linear,
          repeat: -1,
          paused: true,
        }),
      ];

      gsap.to(q("[data-orbit-hub]"), {
        scale: 1.04,
        duration: 2.8,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
      });

      ScrollTrigger.create({
        trigger: scope.current,
        start: "top bottom",
        end: "bottom top",
        onToggle: (self) =>
          spins.forEach((spin) => (self.isActive ? spin.play() : spin.pause())),
      });
    },
    { scope, dependencies: [tier] },
  );

  return (
    <div
      ref={scope}
      aria-hidden="true"
      className="relative mx-auto mb-16 hidden aspect-square w-full max-w-2xl lg:block"
    >
      {/* Ring guides. */}
      <span className="absolute left-1/2 top-1/2 size-[260px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-border/60" />
      <span className="absolute left-1/2 top-1/2 size-[440px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-border/40" />

      {/* Hub. */}
      <span
        data-orbit-hub
        className="absolute left-1/2 top-1/2 flex size-20 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-brand-gradient text-white shadow-elevation-3"
      >
        <Bot className="size-8" />
      </span>

      {/* Rotating ring containers. */}
      <div data-ring="inner" className="absolute inset-0">
        <OrbitBadges ring="inner" radius={INNER_RADIUS} />
      </div>
      <div data-ring="outer" className="absolute inset-0">
        <OrbitBadges ring="outer" radius={OUTER_RADIUS} />
      </div>
    </div>
  );
}
