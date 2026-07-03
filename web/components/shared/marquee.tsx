"use client";

import { useRef, type ReactNode } from "react";

import { useMotion } from "@/lib/gsap/gsap-provider";
import { eases } from "@/lib/gsap/motion";
import { gsap, ScrollTrigger, useGSAP } from "@/lib/gsap/register";
import { cn } from "@/lib/utils";

interface MarqueeProps {
  /** Seconds for one full loop. */
  speed?: number;
  direction?: "left" | "right";
  /** Slows to 10% on hover instead of freezing — feels deliberate, not broken. */
  pauseOnHover?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Infinite scroller (spec §0.5). Content is duplicated for the loop; the
 * clone is aria-hidden. The tween pauses off-screen and never starts under
 * reduced motion (content simply rests at its initial position).
 */
export function Marquee({
  speed = 40,
  direction = "left",
  pauseOnHover = true,
  className,
  children,
}: MarqueeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tweenRef = useRef<gsap.core.Tween | null>(null);
  const { tier } = useMotion();

  useGSAP(
    () => {
      if (tier === "none" || !containerRef.current) return;
      const track = containerRef.current.querySelector("[data-marquee-track]");
      if (!track) return;

      tweenRef.current = gsap.fromTo(
        track,
        { xPercent: direction === "left" ? 0 : -50 },
        {
          xPercent: direction === "left" ? -50 : 0,
          duration: speed,
          ease: eases.linear,
          repeat: -1,
        },
      );

      ScrollTrigger.create({
        trigger: containerRef.current,
        start: "top bottom",
        end: "bottom top",
        onToggle: (self) => {
          if (self.isActive) tweenRef.current?.play();
          else tweenRef.current?.pause();
        },
      });
    },
    { scope: containerRef, dependencies: [tier, direction, speed] },
  );

  const setSpeed = (scale: number) => {
    if (!pauseOnHover || !tweenRef.current) return;
    gsap.to(tweenRef.current, { timeScale: scale, duration: 0.6 });
  };

  return (
    <div
      ref={containerRef}
      className={cn("edge-fade-x overflow-hidden", className)}
      onMouseEnter={() => setSpeed(0.1)}
      onMouseLeave={() => setSpeed(1)}
      onFocus={() => setSpeed(0.1)}
      onBlur={() => setSpeed(1)}
    >
      <div data-marquee-track className="flex w-max">
        <div className="flex shrink-0 items-center">{children}</div>
        <div aria-hidden="true" className="flex shrink-0 items-center">
          {children}
        </div>
      </div>
    </div>
  );
}
