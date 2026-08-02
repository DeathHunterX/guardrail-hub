"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { settingsNavigation } from "@/content/app";
import { cn } from "@/lib/utils";

/**
 * Settings left navigation (horizontal scroll row below `lg`). Grouped into
 * Account and Application per content/app.ts.
 */
export function SettingsNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Settings"
      className="flex gap-1 overflow-x-auto pb-2 lg:w-52 lg:shrink-0 lg:flex-col lg:gap-6 lg:pb-0"
    >
      {settingsNavigation.map((group) => (
        <div key={group.label} className="flex gap-1 lg:block">
          <p className="sr-only px-3 text-[11px] font-medium uppercase tracking-widest text-muted-foreground lg:not-sr-only lg:mb-2">
            {group.label}
          </p>
          <ul className="flex gap-1 lg:block lg:space-y-0.5">
            {group.items.map((item) => {
              const active = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-accent font-medium text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                    )}
                  >
                    <item.icon className="size-4 shrink-0" aria-hidden="true" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
