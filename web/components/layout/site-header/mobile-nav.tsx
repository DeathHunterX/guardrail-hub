"use client";

import { ArrowUpRight, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { siteConfig } from "@/config/site";
import { navigation } from "@/content/site";
import { useMotion } from "@/providers/gsap-provider";
import { durations, eases, staggers } from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";

/**
 * Mobile navigation (spec §2): right-side sheet, accordion groups, staggered
 * link reveal, CTAs pinned to the bottom.
 */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const { tier } = useMotion();
  const pathname = usePathname();

  /** Resolves a link's destination — landing-only anchors apply on "/". */
  const resolveHref = (link: { href: string; landingHref?: string }) =>
    pathname === "/" && link.landingHref ? link.landingHref : link.href;

  useGSAP(
    () => {
      if (!open || tier === "none" || !contentRef.current) return;
      gsap.from("[data-sheet-item]", {
        x: 24,
        autoAlpha: 0,
        duration: durations.sm,
        ease: eases.enter,
        stagger: staggers.tight,
        delay: durations.xs,
      });
    },
    { scope: contentRef, dependencies: [open, tier] },
  );

  const close = () => setOpen(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu aria-hidden />
        </Button>
      </SheetTrigger>
      <SheetContent ref={contentRef} side="right" className="flex w-full flex-col p-0">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle className="text-left text-base">Menu</SheetTitle>
        </SheetHeader>
        <nav
          aria-label="Mobile"
          className="flex-1 overflow-y-auto px-6 py-2"
        >
          <Accordion
            type="multiple"
            defaultValue={navigation.groups.map((group) => group.label)}
          >
            {navigation.groups.map((group) => (
              <AccordionItem key={group.label} value={group.label}>
                <span data-sheet-item className="block">
                  <AccordionTrigger className="text-base">
                    {group.label}
                  </AccordionTrigger>
                </span>
                <AccordionContent>
                  <ul className="flex flex-col gap-1">
                    {group.items.map((item) => (
                      <li key={`${group.label}-${item.label}`} data-sheet-item>
                        <Link
                          href={item.href}
                          onClick={close}
                          className="flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-accent"
                        >
                          <item.icon
                            className="size-4 text-primary"
                            aria-hidden
                          />
                          <span className="text-sm font-medium">
                            {item.label}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
          <ul className="flex flex-col py-2">
            {navigation.links.map((link) => (
              <li key={link.label} data-sheet-item>
                {link.external ? (
                  <a
                    href={link.href}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between rounded-lg px-2 py-3 text-base font-medium transition-colors hover:bg-accent"
                  >
                    {link.label}
                    <ArrowUpRight
                      className="size-4 text-muted-foreground"
                      aria-hidden
                    />
                  </a>
                ) : (
                  <Link
                    href={resolveHref(link)}
                    onClick={close}
                    className="block rounded-lg px-2 py-3 text-base font-medium transition-colors hover:bg-accent"
                  >
                    {link.label}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </nav>
        <div className="grid gap-2 border-t px-6 py-4">
          <Button asChild variant="outline">
            <Link href={siteConfig.app.signIn} onClick={close}>
              Sign in
            </Link>
          </Button>
          <Button asChild className="btn-sheen">
            <Link href={siteConfig.app.signUp} onClick={close}>
              Start Free
            </Link>
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
