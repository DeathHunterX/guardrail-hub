"use client";

import { useRef } from "react";

import { Container } from "@/components/shared/container";
import { Logo } from "@/components/layout/logo";
import { useMotion } from "@/lib/gsap/gsap-provider";
import { durations, eases, staggers } from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";
import { cn } from "@/lib/utils";

import { HeaderActions } from "./header-actions";
import { MainNav } from "./main-nav";
import { MobileNav } from "./mobile-nav";
import { useHeaderScroll } from "./use-header-scroll";

interface HeaderClientProps {
  stars: number | null;
}

/**
 * Sticky header (spec §2). Transparent over the hero; gains a glass surface,
 * hairline border, and compressed height once scrolled 24px. The entrance
 * staggers `[data-header-item]` children top-down and then signals the hero
 * to start (architecture §11 entrance coordination).
 */
export function HeaderClient({ stars }: HeaderClientProps) {
  const headerRef = useRef<HTMLElement>(null);
  const scrolled = useHeaderScroll();
  const { tier, signalEntranceDone } = useMotion();

  useGSAP(
    () => {
      if (tier === "none") {
        signalEntranceDone();
        return;
      }
      gsap.from("[data-header-item]", {
        y: -12,
        autoAlpha: 0,
        duration: durations.sm,
        ease: eases.enter,
        stagger: staggers.tight,
        // The announcement bar slides in first; the header follows.
        delay: durations.sm,
        onComplete: signalEntranceDone,
      });
    },
    { scope: headerRef, dependencies: [tier] },
  );

  return (
    <header
      ref={headerRef}
      className={cn(
        "sticky top-0 z-50 w-full border-b transition-[background-color,border-color,box-shadow] duration-300",
        scrolled
          ? "border-border bg-background/75 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60"
          : "border-transparent bg-transparent",
      )}
    >
      <Container>
        <div
          className={cn(
            "flex items-center justify-between gap-4 transition-[height] duration-300",
            scrolled ? "h-14" : "h-16",
          )}
        >
          <span data-header-item className="flex shrink-0">
            <Logo />
          </span>
          <span data-header-item className="hidden lg:flex">
            <MainNav />
          </span>
          <div className="flex items-center gap-2">
            <HeaderActions stars={stars} />
            <span data-header-item className="flex lg:hidden">
              <MobileNav />
            </span>
          </div>
        </div>
      </Container>
    </header>
  );
}
