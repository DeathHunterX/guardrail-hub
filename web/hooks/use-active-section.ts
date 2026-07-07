"use client";

import { useEffect, useState } from "react";

import { ScrollTrigger } from "@/lib/gsap/register";

/**
 * Tracks which landing section currently occupies the viewport center, for
 * the nav's active-link indicator (spec §2). Sections that are not mounted
 * yet simply create no trigger — the hook activates automatically as
 * sections ship.
 */
export function useActiveSection(ids: readonly string[]): string | null {
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    const triggers = ids.flatMap((id) => {
      const element = document.getElementById(id);
      if (!element) return [];
      return [
        ScrollTrigger.create({
          trigger: element,
          start: "top center",
          end: "bottom center",
          onToggle: (self) => {
            if (self.isActive) {
              setActiveId(id);
            } else {
              setActiveId((current) => (current === id ? null : current));
            }
          },
        }),
      ];
    });

    return () => triggers.forEach((trigger) => trigger.kill());
  }, [ids]);

  return activeId;
}
