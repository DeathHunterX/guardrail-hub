"use client";

import { ArrowUpRight, ChevronDown, Plug } from "lucide-react";
import { useRef, useState } from "react";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { siteConfig } from "@/config/site";
import { useMotion } from "@/lib/gsap/gsap-provider";
import { durations, eases, staggers } from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";

import { categories, integrations } from "./integrations.data";

type CategoryId = (typeof categories)[number]["id"];

/**
 * The accessible, filterable source of truth for every integration.
 * "All" is the default so the grid always opens visually full and balanced.
 */
export function IntegrationGrid() {
  const scope = useRef<HTMLDivElement>(null);
  const [category, setCategory] = useState<CategoryId>("all");
  const { tier } = useMotion();

  const visible =
    category === "all"
      ? integrations
      : integrations.filter((item) => item.category === category);

  useGSAP(
    () => {
      if (tier === "none" || !scope.current) return;
      gsap.fromTo(
        scope.current.querySelectorAll("[data-logo-card]"),
        { y: 12, autoAlpha: 0 },
        {
          y: 0,
          autoAlpha: 1,
          duration: durations.sm,
          ease: eases.enter,
          stagger: staggers.tight / 2,
          overwrite: true,
        },
      );
    },
    { scope, dependencies: [tier, category] },
  );

  return (
    <div ref={scope}>
      {/* Mobile: a native select — the tab bar overflows below `sm` and
          wraps its last category onto a stray second line. */}
      <div className="relative sm:hidden">
        <label className="sr-only" htmlFor="integration-category">
          Integration category
        </label>
        <select
          id="integration-category"
          value={category}
          onChange={(event) => setCategory(event.target.value as CategoryId)}
          className="h-10 w-full appearance-none rounded-xl border bg-card px-3 pr-9 text-sm font-medium outline-none transition-colors focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
        >
          {categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
      </div>

      {/* Tablet and up: the original tab bar. */}
      <Tabs
        value={category}
        onValueChange={(value) => setCategory(value as CategoryId)}
        className="hidden flex-col items-center sm:flex"
      >
        <TabsList aria-label="Integration categories" className="max-w-full flex-wrap justify-center gap-y-1 sm:h-9">
          {categories.map((item) => (
            <TabsTrigger key={item.id} value={item.id}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((item) => (
          <li key={item.name} data-logo-card>
            <article className="group flex h-full items-start gap-3 rounded-2xl border bg-card p-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-elevation-2 motion-reduce:hover:translate-y-0">
              <span className="icon-tile size-9 rounded-md">
                <Plug className="size-4" aria-hidden />
              </span>
              <span>
                <span className="block text-sm font-semibold">{item.name}</span>
                <span className="block text-xs leading-relaxed text-muted-foreground">
                  {item.description}
                </span>
              </span>
            </article>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-center text-sm text-muted-foreground">
        Something missing? The toolbelt keeps growing — and the agent speaks
        CLI, so you can bring any tool.{" "}
        <a
          href={siteConfig.links.docs}
          target="_blank"
          rel="noreferrer"
          className="group inline-flex items-center gap-0.5 font-medium text-primary"
        >
          Integration docs
          <ArrowUpRight
            className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
            aria-hidden
          />
        </a>
      </p>
    </div>
  );
}
