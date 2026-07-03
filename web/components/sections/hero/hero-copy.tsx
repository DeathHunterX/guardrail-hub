"use client";

import { Bot, Check } from "lucide-react";
import { useRef } from "react";

import { CTAGroup } from "@/components/shared/cta-group";
import { GradientText } from "@/components/shared/gradient-text";
import { Badge } from "@/components/ui/badge";
import { siteConfig } from "@/config/site";
import { useMotion } from "@/lib/gsap/gsap-provider";
import {
  durations,
  eases,
  introStartAfterLoad,
  shouldPlayIntro,
  staggers,
} from "@/lib/gsap/motion";
import { gsap, SplitText, useGSAP } from "@/lib/gsap/register";

import { heroCopy } from "./hero.data";

/**
 * Hero copy column (spec §3). The H1 rises word by word via SplitText after
 * the header entrance settles; supporting elements follow with the house
 * stagger. Reduced motion: everything is simply present.
 */
export function HeroCopy() {
  const scope = useRef<HTMLDivElement>(null);
  const { tier, entranceDone } = useMotion();
  // Decide once at mount: on late hydration or a restored scroll position
  // the SSR copy has been readable for a while — replaying the intro would
  // hide it and read as a glitch, so we keep the static final state.
  const playIntro = useRef(shouldPlayIntro());

  useGSAP(
    () => {
      if (tier === "none" || !entranceDone || !scope.current) return;
      if (!playIntro.current) return;
      const heading = scope.current.querySelector("h1");
      if (!heading) return;

      const split = SplitText.create(heading, { type: "words" });
      const tl = gsap.timeline({
        defaults: { ease: eases.enter },
        paused: true,
      });
      tl.from(split.words, {
        y: 28,
        autoAlpha: 0,
        duration: durations.md,
        stagger: staggers.tight,
        onComplete: () => split.revert(),
        // Defer the hidden start state until the timeline actually plays —
        // the copy must stay readable during the pre-intro pause.
        immediateRender: false,
      });
      tl.from(
        "[data-hero-item]",
        {
          y: 20,
          autoAlpha: 0,
          duration: durations.md,
          stagger: staggers.base,
        },
        "-=0.3",
      );

      // The intro starts a fixed beat (~3.2s) after page load, so after a
      // refresh the copy stays readable for a moment and then animates in
      // predictably, together with the workspace story next to it.
      const delay = Math.max(0, introStartAfterLoad - performance.now() / 1000);
      gsap.delayedCall(delay, () => tl.play());
    },
    { scope, dependencies: [tier, entranceDone] },
  );

  return (
    <div ref={scope} className="max-w-xl">
      <span data-hero-item className="inline-flex">
        <Badge variant="outline" className="gap-1.5 py-1 pl-1.5 pr-3">
          <span className="flex size-5 items-center justify-center rounded-full bg-primary/10">
            <Bot className="size-3 text-primary" aria-hidden />
          </span>
          {heroCopy.eyebrow}
        </Badge>
      </span>
      <h1 className="mt-5 text-balance text-display">
        {heroCopy.headline.lead}{" "}
        <GradientText>{heroCopy.headline.highlight}</GradientText>
      </h1>
      <p
        data-hero-item
        className="mt-5 text-pretty text-lg leading-relaxed text-muted-foreground"
      >
        {heroCopy.description}
      </p>
      <div data-hero-item className="mt-8">
        <CTAGroup
          primary={{ label: "Start Free", href: siteConfig.app.signUp }}
          secondary={{ label: "Book Demo", href: siteConfig.app.bookDemo }}
          tertiary={[
            {
              label: "View Documentation",
              href: siteConfig.links.docs,
              external: true,
            },
            {
              label: "Explore GitHub",
              href: siteConfig.links.github,
              external: true,
            },
          ]}
        />
      </div>
      <ul
        data-hero-item
        className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground"
      >
        {heroCopy.trust.map((item) => (
          <li key={item} className="flex items-center gap-1.5">
            <Check className="size-3.5 text-success" aria-hidden />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
