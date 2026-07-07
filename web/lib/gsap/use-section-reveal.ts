"use client";

import { useRef, type RefObject } from "react";

import { useMotion } from "@/providers/gsap-provider";
import {
  durations,
  eases,
  fastScrollVelocity,
  revealStart,
  revealStartCompact,
  revealStartFraction,
  revealStartFractionCompact,
  staggers,
} from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";

/**
 * The house-style section reveal (spec §0.6): children marked with
 * `data-reveal` rise 24px with a stagger when the section enters at 75%
 * viewport. DOM order is the default sequence; `data-reveal-order` overrides.
 *
 * Under the "none" tier nothing runs — SSR HTML is already the final state.
 */
export function useSectionReveal<T extends HTMLElement>(): RefObject<T | null> {
  const scope = useRef<T>(null);
  const { tier } = useMotion();

  useGSAP(
    () => {
      if (tier === "none" || !scope.current) return;

      const targets = gsap.utils
        .toArray<HTMLElement>("[data-reveal]", scope.current)
        .sort((a, b) => {
          const orderA = Number(a.dataset.revealOrder ?? Number.MAX_SAFE_INTEGER);
          const orderB = Number(b.dataset.revealOrder ?? Number.MAX_SAFE_INTEGER);
          return orderA - orderB;
        });

      if (targets.length === 0) return;

      // Compact viewports reveal earlier and faster — on phones/tablets a
      // late, slow reveal reads as content that failed to load in time.
      const isCompact = tier === "compact";
      const startFraction = isCompact
        ? revealStartFractionCompact
        : revealStartFraction;

      // If the section is already inside the trigger zone when this effect
      // runs (restored scroll position, late hydration), skip the animation
      // entirely: the SSR markup is already the correct final state, and
      // hiding it just to replay the reveal would flash the content away.
      const alreadyInView =
        scope.current.getBoundingClientRect().top <
        window.innerHeight * startFraction;
      if (alreadyInView) return;

      gsap.from(targets, {
        y: 24,
        autoAlpha: 0,
        duration: isCompact ? durations.sm : durations.md,
        ease: eases.enter,
        stagger: isCompact ? staggers.tight : staggers.base,
        scrollTrigger: {
          trigger: scope.current,
          start: isCompact ? revealStartCompact : revealStart,
          once: true,
          // A fast fling means the reader is already past this section:
          // snap the reveal to its end instead of trailing them with a
          // late animation that reads as content loading slowly.
          onEnter: (self) => {
            if (Math.abs(self.getVelocity()) > fastScrollVelocity) {
              self.animation?.progress(1);
            }
          },
        },
        // Failsafe: strip the inline styles once the reveal finishes so no
        // element can ever stay stuck invisible after re-renders/refreshes.
        onComplete: () =>
          gsap.set(targets, { clearProps: "opacity,visibility,transform" }),
      });
    },
    { scope, dependencies: [tier] },
  );

  return scope;
}
