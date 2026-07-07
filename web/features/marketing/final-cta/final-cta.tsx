"use client";

import { ShieldCheck } from "lucide-react";
import { useRef } from "react";

import { Container } from "@/components/common/container";
import { CTAGroup } from "@/components/common/cta-group";
import { siteConfig } from "@/config/site";
import { useMotion } from "@/providers/gsap-provider";
import { durations, eases, fastScrollVelocity, staggers } from "@/lib/gsap/motion";
import { gsap, ScrollTrigger, useGSAP } from "@/lib/gsap/register";

const PARTICLE_COUNT = 14;

/**
 * Final CTA (spec §15): the richest use of the signature gradient on the
 * page, with the data-flow motif converging toward the primary action.
 * Text sits on the saturated panel, so white literals are correct here.
 */
export function FinalCTA() {
  const scope = useRef<HTMLElement>(null);
  const { tier } = useMotion();

  useGSAP(
    () => {
      if (tier === "none" || !scope.current) return;
      const q = gsap.utils.selector(scope.current);
      const isCompact = tier === "compact";

      // Snap a reveal to its final state when the reader flings past it.
      const finishOnFastScroll = (self: ScrollTrigger) => {
        if (Math.abs(self.getVelocity()) > fastScrollVelocity) {
          self.animation?.progress(1);
        }
      };

      // Skip the entrance when the section is already in view (restored
      // scroll, late hydration) — the SSR markup is the correct final state.
      const alreadyInView =
        scope.current.getBoundingClientRect().top <
        window.innerHeight * (isCompact ? 0.92 : 0.85);

      if (!alreadyInView) {
        // Refresh-proof reveal: set + .to (never reverted by ScrollTrigger.refresh).
        gsap.set(q("[data-cta-panel]"), { scale: 0.96, autoAlpha: 0 });
        gsap.set(q("[data-cta-item]"), { y: 24, autoAlpha: 0 });
        gsap.to(q("[data-cta-panel]"), {
          scale: 1,
          autoAlpha: 1,
          duration: durations.lg,
          ease: eases.land,
          scrollTrigger: {
            trigger: scope.current,
            start: isCompact ? "top 90%" : "top 70%",
            once: true,
            onEnter: finishOnFastScroll,
          },
        });
        gsap.to(q("[data-cta-item]"), {
          y: 0,
          autoAlpha: 1,
          duration: durations.md,
          ease: eases.enter,
          stagger: isCompact ? staggers.tight : staggers.base,
          scrollTrigger: {
            trigger: scope.current,
            start: isCompact ? "top 88%" : "top 65%",
            once: true,
            onEnter: finishOnFastScroll,
          },
        });
      }

      // Particles drift toward the CTA block; paused off-screen.
      const drifts = q("[data-particle]").map((particle, index) =>
        gsap.to(particle, {
          x: gsap.utils.random(-60, 60),
          y: gsap.utils.random(-40, 40),
          opacity: gsap.utils.random(0.15, 0.5),
          duration: gsap.utils.random(6, 10),
          ease: "sine.inOut",
          yoyo: true,
          repeat: -1,
          delay: index * 0.3,
          paused: true,
        }),
      );
      ScrollTrigger.create({
        trigger: scope.current,
        start: "top bottom",
        end: "bottom top",
        onToggle: (self) =>
          drifts.forEach((d) => (self.isActive ? d.play() : d.pause())),
      });
    },
    { scope, dependencies: [tier] },
  );

  return (
    <section
      ref={scope}
      aria-labelledby="final-cta-heading"
      className="py-12 md:py-14"
    >
      <Container>
        <div
          data-cta-panel
          className="relative isolate overflow-hidden rounded-3xl bg-brand-gradient px-6 py-20 text-center md:px-8 md:py-28"
          data-theme-static
        >
          <div aria-hidden="true" className="absolute inset-0 -z-10">
            {Array.from({ length: PARTICLE_COUNT }, (_, index) => (
              <span
                key={index}
                data-particle
                className="absolute size-1.5 rounded-full bg-white/30"
                style={{
                  left: `${8 + ((index * 6.3) % 84)}%`,
                  top: `${12 + ((index * 11.7) % 72)}%`,
                }}
              />
            ))}
          </div>
          <span
            data-cta-item
            className="mx-auto flex size-12 items-center justify-center rounded-xl bg-white/15 text-white"
          >
            <ShieldCheck className="size-6" aria-hidden />
          </span>
          <h2
            data-cta-item
            id="final-cta-heading"
            className="mx-auto mt-6 max-w-2xl text-balance text-heading-2 text-white"
          >
            Your next release, already validated.
          </h2>
          <p
            data-cta-item
            className="mx-auto mt-4 max-w-xl text-pretty text-white/80"
          >
            Point the agent at a URL. Get your first security report in
            minutes — free.
          </p>
          <div data-cta-item className="mt-8">
            <CTAGroup
              align="center"
              size="xl"
              tone="onGradient"
              primary={{ label: "Start Free", href: siteConfig.app.signUp }}
              secondary={{ label: "Book Demo", href: siteConfig.app.bookDemo }}
            />
          </div>
          <p data-cta-item className="mt-6 text-sm text-white/60">
            Free tier forever · No credit card · SOC 2 Type II
          </p>
        </div>
      </Container>
    </section>
  );
}
